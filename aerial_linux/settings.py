#!/usr/bin/env python3
"""Aerial Views Ayarları (GTK4 / libadwaita)."""

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from aerial_linux import config as cfgmod  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
SERVICE = "aerial-daemon.service"


def systemctl(*args):
    try:
        r = subprocess.run(["systemctl", "--user", *args],
                           capture_output=True, text=True, timeout=10)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def get_cache_size_mb():
    try:
        if not os.path.exists(cfgmod.CACHE_DIR):
            return 0.0
        total = sum(
            os.path.getsize(os.path.join(cfgmod.CACHE_DIR, f))
            for f in os.listdir(cfgmod.CACHE_DIR)
            if os.path.isfile(os.path.join(cfgmod.CACHE_DIR, f))
        )
        return total / (1024 * 1024)
    except Exception:
        return 0.0


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Aerial Views Ayarları")
        self.set_default_size(980, 620)
        self.cfg = cfgmod.load()
        self._save_src = None

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                        margin_top=12, margin_bottom=18,
                        margin_start=18, margin_end=18)
        columns = Gtk.Box(spacing=18, homogeneous=True)
        outer.append(columns)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(outer)
        toolbar.set_content(scroller)
        self.set_content(toolbar)

        col_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        col_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        columns.append(col_left)
        columns.append(col_right)

        # ================= SOL SÜTUN =================
        # --- Ekran Koruyucu ---
        g1 = Adw.PreferencesGroup(
            title="Ekran Koruyucu",
            description="Bilgisayar boşta kaldığında Apple Aerial video manzarasını başlatır."
        )
        col_left.append(g1)

        self.sw_enabled = Adw.SwitchRow(title="Etkin")
        self.sw_enabled.set_active(self.cfg.enabled)
        self.sw_enabled.connect("notify::active", self._changed)
        g1.add(self.sw_enabled)

        self.sp_idle = Adw.SpinRow.new_with_range(0.5, 240, 0.5)
        self.sp_idle.set_title("Boşta kalma süresi (dakika)")
        self.sp_idle.set_digits(1)
        self.sp_idle.set_value(self.cfg.idle_minutes)
        self.sp_idle.connect("notify::value", self._changed)
        g1.add(self.sp_idle)

        self.sw_inhibit = Adw.SwitchRow(
            title="Video oynarken başlatma",
            subtitle="Uygulamalar boşta kalmayı engellediğinde (video, sunum) başlatma"
        )
        self.sw_inhibit.set_active(self.cfg.respect_inhibit)
        self.sw_inhibit.connect("notify::active", self._changed)
        g1.add(self.sw_inhibit)

        self.sw_lock = Adw.SwitchRow(
            title="Çıkarken ekranı kilitle",
            subtitle="Geri döndüğünüzde kilit ekranı açılır (parola gerekir)"
        )
        self.sw_lock.set_active(self.cfg.lock_on_exit)
        self.sw_lock.connect("notify::active", self._changed)
        self.sw_lock.connect("notify::active", lambda *_: self.combo_lock_mode.set_sensitive(self.sw_lock.get_active()))
        g1.add(self.sw_lock)

        self.combo_lock_mode = Adw.ComboRow(
            title="Kilit ekranı tarzı",
            subtitle="macOS tarzında şifre girilmezse kutu kaybolur ve manzara oynamaya devam eder"
        )
        model = Gtk.StringList.new(["macOS Tarzı (Entegre Şifre & Geri Çekilme)", "Ubuntu / GNOME Kilit Ekranı"])
        self.combo_lock_mode.set_model(model)
        self.combo_lock_mode.set_selected(0 if self.cfg.lock_mode == "macos" else 1)
        self.combo_lock_mode.set_sensitive(self.cfg.lock_on_exit)
        self.combo_lock_mode.connect("notify::selected", self._changed)
        g1.add(self.combo_lock_mode)

        self.status_row = Adw.ActionRow(title="Servis durumu")
        btn_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)

        self.btn_toggle_service = Gtk.Button(label="Durdur", valign=Gtk.Align.CENTER)
        self.btn_toggle_service.connect("clicked", self._toggle_service)

        self.btn_restart_service = Gtk.Button(label="Yeniden başlat", valign=Gtk.Align.CENTER)
        self.btn_restart_service.connect("clicked", self._restart_service)

        btn_box.append(self.btn_toggle_service)
        btn_box.append(self.btn_restart_service)
        self.status_row.add_suffix(btn_box)
        g1.add(self.status_row)

        # --- Önbellek & Depolama ---
        g_cache = Adw.PreferencesGroup(title="Önbellek ve Depolama")
        col_left.append(g_cache)

        self.sw_cache = Adw.SwitchRow(
            title="İzlenen videoları diske kaydet",
            subtitle="Bir sonraki oynatmada internet harcamadan doğrudan diskten oynatır"
        )
        self.sw_cache.set_active(self.cfg.cache_enabled)
        self.sw_cache.connect("notify::active", self._changed)
        g_cache.add(self.sw_cache)

        self.sp_cache_limit = Adw.SpinRow.new_with_range(1, 50, 1)
        self.sp_cache_limit.set_title("Maksimum önbellek boyutu (GB)")
        self.sp_cache_limit.set_value(self.cfg.cache_limit_gb)
        self.sp_cache_limit.connect("notify::value", self._changed)
        g_cache.add(self.sp_cache_limit)

        self.cache_info_row = Adw.ActionRow(title="Disk kullanımı")
        btn_clear_cache = Gtk.Button(label="Temizle", valign=Gtk.Align.CENTER)
        btn_clear_cache.add_css_class("destructive-action")
        btn_clear_cache.connect("clicked", self._clear_cache)
        self.cache_info_row.add_suffix(btn_clear_cache)
        g_cache.add(self.cache_info_row)

        # ================= SAĞ SÜTUN =================
        # --- Görünüm & Video ---
        g2 = Adw.PreferencesGroup(title="Görünüm ve Video")
        col_right.append(g2)

        # Kalite seçimi
        self.combo_quality = Adw.ComboRow(title="Video Kalitesi")
        qualities = Gtk.StringList.new([
            "1080p H.264 (Hızlı ve Evrensel)",
            "1080p HEVC (Yüksek Verimli)",
            "4K Ultra HD (HEVC / Apple Orijinal)"
        ])
        self.combo_quality.set_model(qualities)
        q_idx = {"1080p-h264": 0, "1080p-hevc": 1, "4k-hevc": 2}.get(self.cfg.quality, 0)
        self.combo_quality.set_selected(q_idx)
        self.combo_quality.connect("notify::selected", self._changed)
        g2.add(self.combo_quality)

        self.sw_loc = Adw.SwitchRow(
            title="Konum bilgisini göster",
            subtitle="Sol altta şehir ve manzara detayını gösterir"
        )
        self.sw_loc.set_active(self.cfg.show_location)
        self.sw_loc.connect("notify::active", self._changed)
        g2.add(self.sw_loc)

        self.sw_clock = Adw.SwitchRow(
            title="Saati göster",
            subtitle="Sağ altta zarif dijital saat ve tarih"
        )
        self.sw_clock.set_active(self.cfg.show_clock)
        self.sw_clock.connect("notify::active", self._changed)
        g2.add(self.sw_clock)

        self.sw_24h = Adw.SwitchRow(title="24 saat biçimi")
        self.sw_24h.set_active(self.cfg.clock_24h)
        self.sw_24h.connect("notify::active", self._changed)
        g2.add(self.sw_24h)

        self.sw_sync = Adw.SwitchRow(
            title="Gündüz / Gece uyumu",
            subtitle="Gündüzleri güneşli çekimler, geceleri şehir ışıkları oynatılır"
        )
        self.sw_sync.set_active(self.cfg.time_sync)
        self.sw_sync.connect("notify::active", self._changed)
        g2.add(self.sw_sync)

        self.combo_lang = Adw.ComboRow(title="Bilgi Dili")
        langs = Gtk.StringList.new(["Türkçe", "English"])
        self.combo_lang.set_model(langs)
        self.combo_lang.set_selected(0 if self.cfg.language == "tr" else 1)
        self.combo_lang.connect("notify::selected", self._changed)
        g2.add(self.combo_lang)

        self.sw_all = Adw.SwitchRow(
            title="Tüm monitörlerde göster",
            subtitle="Bağlı tüm ekranlarda (laptop + 4K monitör) bağımsız manzaralar oynatır"
        )
        self.sw_all.set_active(self.cfg.all_monitors)
        self.sw_all.connect("notify::active", self._changed)
        g2.add(self.sw_all)

        # ================= ALT BUTONLAR =================
        box_buttons = Gtk.Box(spacing=14, halign=Gtk.Align.CENTER, margin_top=8)
        btn_preview = Gtk.Button(label="Pencerede Önizle")
        btn_preview.connect("clicked", lambda *_: self._launch(["--preview"]))

        btn_run = Gtk.Button(label="Şimdi Başlat (Tam Ekran)")
        btn_run.add_css_class("suggested-action")
        btn_run.connect("clicked", lambda *_: self._launch([]))

        box_buttons.append(btn_preview)
        box_buttons.append(btn_run)
        outer.append(box_buttons)

        self._refresh_status()
        self._refresh_cache_info()
        GLib.timeout_add_seconds(3, self._refresh_status)

    def _changed(self, *_):
        if self._save_src is not None:
            GLib.source_remove(self._save_src)
        self._save_src = GLib.timeout_add(250, self._save)

    def _save(self):
        self._save_src = None
        c = self.cfg
        c.enabled = self.sw_enabled.get_active()
        c.idle_minutes = self.sp_idle.get_value()
        c.respect_inhibit = self.sw_inhibit.get_active()
        c.lock_on_exit = self.sw_lock.get_active()
        c.lock_mode = "macos" if self.combo_lock_mode.get_selected() == 0 else "gnome"

        q_map = {0: "1080p-h264", 1: "1080p-hevc", 2: "4k-hevc"}
        c.quality = q_map.get(self.combo_quality.get_selected(), "1080p-h264")
        c.show_location = self.sw_loc.get_active()
        c.show_clock = self.sw_clock.get_active()
        c.clock_24h = self.sw_24h.get_active()
        c.time_sync = self.sw_sync.get_active()
        c.language = "tr" if self.combo_lang.get_selected() == 0 else "en"
        c.all_monitors = self.sw_all.get_active()

        c.cache_enabled = self.sw_cache.get_active()
        c.cache_limit_gb = self.sp_cache_limit.get_value()

        try:
            cfgmod.save(c)
        except OSError as e:
            self.status_row.set_subtitle(f"Ayarlar kaydedilemedi: {e}")
        return GLib.SOURCE_REMOVE

    def flush(self):
        if self._save_src is not None:
            GLib.source_remove(self._save_src)
            self._save()

    def _launch(self, extra):
        self.flush()
        args = [sys.executable, os.path.join(HERE, "player.py"), *extra]
        try:
            Gio.Subprocess.new(args, Gio.SubprocessFlags.NONE)
        except GLib.Error as e:
            self.status_row.set_subtitle(f"Başlatılamadı: {e.message}")

    def _refresh_status(self):
        rc, out = systemctl("is-active", SERVICE)
        if out == "active":
            self.status_row.set_subtitle("Çalışıyor ✓")
            self.btn_toggle_service.set_label("Durdur")
            self.btn_toggle_service.remove_css_class("suggested-action")
            self.btn_toggle_service.add_css_class("destructive-action")
            self.btn_restart_service.set_sensitive(True)
        else:
            self.status_row.set_subtitle(f"Durduruldu ({out})" if out else "Durduruldu")
            self.btn_toggle_service.set_label("Başlat")
            self.btn_toggle_service.remove_css_class("destructive-action")
            self.btn_toggle_service.add_css_class("suggested-action")
            self.btn_restart_service.set_sensitive(False)
        return GLib.SOURCE_CONTINUE

    def _toggle_service(self, *_):
        self.flush()
        rc, out = systemctl("is-active", SERVICE)
        if out == "active":
            systemctl("stop", SERVICE)
        else:
            # Aerial başlatıldığında Fliqlo saati durdurulur (çakışmayı önler)
            systemctl("stop", "fliqlo-daemon.service")
            systemctl("start", SERVICE)
        self._refresh_status()

    def _refresh_cache_info(self):
        mb = get_cache_size_mb()
        if mb >= 1024:
            self.cache_info_row.set_subtitle(f"{mb / 1024:.2f} GB disk alanı kullanılıyor")
        else:
            self.cache_info_row.set_subtitle(f"{mb:.1f} MB disk alanı kullanılıyor")

    def _clear_cache(self, *_):
        if os.path.exists(cfgmod.CACHE_DIR):
            shutil.rmtree(cfgmod.CACHE_DIR, ignore_errors=True)
            os.makedirs(cfgmod.CACHE_DIR, exist_ok=True)
        self._refresh_cache_info()

    def _restart_service(self, *_):
        self.flush()
        systemctl("restart", SERVICE)
        self._refresh_status()


class SettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.aerial_linux.Settings")

    def do_activate(self):
        win = self.get_active_window()
        if win is None:
            win = SettingsWindow(self)
            win.connect("close-request", lambda w: (w.flush(), False)[1])
        win.present()


if __name__ == "__main__":
    sys.exit(SettingsApp().run(sys.argv))
