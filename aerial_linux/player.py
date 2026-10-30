#!/usr/bin/env python3
"""Aerial Screensaver Video Oynatıcısı (mpv tabanlı Wayland çoklu monitör oynatıcı)."""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import ssl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from gi.repository import Gio, GLib  # noqa: E402
from aerial_linux import auth  # noqa: E402
from aerial_linux import config as cfgmod  # noqa: E402
from aerial_linux import manifest  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
LUA_SCRIPT = os.path.join(HERE, "overlay.lua")


def get_monitors():
    """Bağlı tüm monitörlerin Wayland konnektör isimlerini döner (örn: ['eDP-1', 'DP-1'])."""
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk, Gdk
        Gtk.init()
        d = Gdk.Display.get_default()
        if not d:
            return []
        mons = d.get_monitors()
        res = []
        for i in range(mons.get_n_items()):
            m = mons.get_item(i)
            connector = getattr(m, 'get_connector', lambda: None)()
            res.append(connector or str(i))
        return res
    except Exception:
        return []


def lock_screen():
    """Çıkarken GNOME oturumunu kilitler."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.gnome.ScreenSaver",
            "/org/gnome/ScreenSaver",
            "org.gnome.ScreenSaver",
            "Lock",
            None,
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None
        )
        return True
    except Exception:
        try:
            subprocess.run(["loginctl", "lock-session"], timeout=2)
            return True
        except Exception:
            return False


def background_cache_worker(item: dict, quality: str, limit_gb: float):
    """Arka planda videoyu diske indirir (varsa ve limit aşılmamışsa)."""
    try:
        os.makedirs(cfgmod.CACHE_DIR, exist_ok=True)
        total_size = sum(
            os.path.getsize(os.path.join(cfgmod.CACHE_DIR, f))
            for f in os.listdir(cfgmod.CACHE_DIR)
            if os.path.isfile(os.path.join(cfgmod.CACHE_DIR, f))
        )
        if total_size > limit_gb * 1024 * 1024 * 1024:
            return

        vid_id = item.get("id") or "vid"
        target_path = os.path.join(cfgmod.CACHE_DIR, f"{vid_id}_{quality}.mov")
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1024 * 1024:
            return

        url = item.get("stream_url")
        if not url or not url.startswith("http"):
            return

        tmp_path = target_path + ".tmp"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers={"User-Agent": "Aerial/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp, open(tmp_path, "wb") as out_f:
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                out_f.write(chunk)
        os.replace(tmp_path, target_path)
    except Exception:
        pass


def play(args):
    cfg = cfgmod.load()
    if args.quality:
        cfg.quality = args.quality
    if args.no_lock:
        cfg.lock_on_exit = False
    if args.show_location is not None:
        cfg.show_location = args.show_location
    if args.show_clock is not None:
        cfg.show_clock = args.show_clock

    playlist = manifest.get_playlist(cfg)
    if not playlist:
        print("[aerial] Oynatılacak video bulunamadı!", file=sys.stderr)
        return 1

    # İlk videoyu arka planda önbelleğe almayı başlat
    if cfg.cache_enabled and not playlist[0].get("is_cached"):
        t = threading.Thread(
            target=background_cache_worker,
            args=(playlist[0], cfg.quality, cfg.cache_limit_gb),
            daemon=True
        )
        t.start()

    # Oynatma listesi dosyası
    temp_files = []
    with tempfile.NamedTemporaryFile("w", suffix=".m3u", delete=False, encoding="utf-8") as f:
        m3u_path = f.name
        temp_files.append(m3u_path)
        for item in playlist:
            f.write(f"{item['play_path']}\n")

    meta_json = json.dumps(playlist, ensure_ascii=False)

    user, full_name, _ = auth.get_user_info()
    parts = [p for p in full_name.split() if p]
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    elif parts:
        initials = parts[0][:2].upper()
    else:
        initials = "U"

    unlock_file = f"/tmp/aerial_unlocked_{os.getpid()}"
    fallback_file = f"/tmp/aerial_fallback_{os.getpid()}"
    active_mon_file = f"/tmp/aerial_active_mon_{os.getpid()}"
    active_focus_file = f"/tmp/aerial_focus_{os.getpid()}"
    temp_files.extend([unlock_file, fallback_file, active_mon_file, active_focus_file])

    def build_mpv_cmd(screen_connector=None, playlist_offset=0):
        cmd = [
            "mpv",
            f"--playlist={m3u_path}",
            f"--playlist-start={playlist_offset}",
            "--loop-playlist=inf",
            "--hwdec=auto",
            "--vo=gpu",
            "--gpu-context=wayland",
            "--no-audio",
            "--really-quiet",
            "--terminal=no",
            "--osc=no",
            "--osd-level=0",
            "--input-default-bindings=no",
            f"--script={LUA_SCRIPT}",
            f"--script-opts="
            f"aerial_show_location={'yes' if cfg.show_location else 'no'},"
            f"aerial_show_clock={'yes' if cfg.show_clock else 'no'},"
            f"aerial_clock_24h={'yes' if cfg.clock_24h else 'no'},"
            f"aerial_preview={'yes' if args.preview else 'no'},"
            f"aerial_lock_on_exit={'yes' if cfg.lock_on_exit else 'no'},"
            f"aerial_lock_mode={cfg.lock_mode},"
            f"aerial_lock_timeout={cfg.lock_timeout},"
            f"aerial_user={user},"
            f"aerial_full_name={full_name},"
            f"aerial_initials={initials},"
            f"aerial_python_bin={sys.executable},"
            f"aerial_auth_script={os.path.join(HERE, 'auth.py')},"
            f"aerial_unlock_file={unlock_file},"
            f"aerial_fallback_file={fallback_file},"
            f"aerial_screen_name={screen_connector or ''},"
            f"aerial_active_mon_file={active_mon_file},"
            f"aerial_focus_file={active_focus_file},"
            f"aerial_meta={meta_json}",
        ]
        if args.preview:
            cmd.extend([
                "--geometry=1280x720",
                "--autofit=1280x720",
                "--title=Aerial Views (Önizleme)"
            ])
        else:
            cmd.extend([
                "--fullscreen=yes",
                "--no-border",
                "--ontop=yes",
                "--panscan=1.0",           # 16:10 ve 4K monitörde kenarları boşluksuz doldurur
                "--cursor-autohide=always", # İmleci gizler
                "--input-cursor=yes",       # Mouse ve Touchpad hareketini algılar
            ])
            if screen_connector:
                cmd.extend([
                    f"--screen-name={screen_connector}",
                    f"--fs-screen-name={screen_connector}"
                ])
        return cmd

    procs = []
    try:
        monitors = get_monitors() if (not args.preview and cfg.all_monitors) else []
        if len(monitors) > 1:
            # Her monitörde farklı bir manzara ile başlat
            offset_step = max(1, len(playlist) // len(monitors))
            for i, mon in enumerate(monitors):
                offset = (i * offset_step) % len(playlist)
                cmd = build_mpv_cmd(screen_connector=mon, playlist_offset=offset)
                p = subprocess.Popen(cmd)
                procs.append(p)
        else:
            p = subprocess.Popen(build_mpv_cmd())
            procs.append(p)

        # Çoklu monitör: herhangi bir ekranda kilit açıldığında veya kapatıldığında tüm pencereleri kapat
        while any(p.poll() is None for p in procs):
            if any(p.poll() is not None for p in procs):
                for p in procs:
                    if p.poll() is None:
                        try:
                            p.terminate()
                        except Exception:
                            pass
                break
            time.sleep(0.05)

    except KeyboardInterrupt:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
    finally:
        unlocked = os.path.exists(unlock_file)
        fallback = os.path.exists(fallback_file)

        for tf in temp_files:
            try:
                os.remove(tf)
            except OSError:
                pass

    if not args.preview and cfg.lock_on_exit:
        if cfg.lock_mode == "macos":
            # macOS modunda şifre doğrulanarak açıldıysa GNOME kilit ekranı açılmaz
            if not unlocked or fallback:
                lock_screen()
        else:
            lock_screen()

    return 0


def main():
    parser = argparse.ArgumentParser(description="Aerial Views Ekran Koruyucusu (macOS tarzı)")
    parser.add_argument("--preview", action="store_true", help="Pencere modunda önizleme (Esc/Q ile çıkar)")
    parser.add_argument("--quality", choices=["1080p-h264", "1080p-hevc", "4k-hevc"], help="Video kalitesi")
    parser.add_argument("--no-lock", action="store_true", help="Kapanırken ekranı kilitleme")
    parser.add_argument("--location", dest="show_location", action="store_const", const=True, help="Konum yazısını göster")
    parser.add_argument("--no-location", dest="show_location", action="store_const", const=False, help="Konum yazısını gizle")
    parser.add_argument("--clock", dest="show_clock", action="store_const", const=True, help="Saati göster")
    parser.add_argument("--no-clock", dest="show_clock", action="store_const", const=False, help="Saati gizle")
    args = parser.parse_args()
    return play(args)


if __name__ == "__main__":
    sys.exit(main())
