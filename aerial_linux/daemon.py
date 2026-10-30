#!/usr/bin/env python3
"""Aerial ekran koruyucu servisi (GNOME / Wayland).

Mutter'ın `org.gnome.Mutter.IdleMonitor` D-Bus arayüzünü kullanarak kullanıcının
boşta kalma süresini izler ve süre dolunca Aerial video oynatıcısını başlatır.
"""

import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from gi.repository import Gio, GLib
from aerial_linux.compat import unix_signal_add  # noqa: E402
from aerial_linux import config as cfgmod  # noqa: E402

IDLE_BUS = "org.gnome.Mutter.IdleMonitor"
IDLE_PATH = "/org/gnome/Mutter/IdleMonitor/Core"
IDLE_IFACE = "org.gnome.Mutter.IdleMonitor"

SM_BUS = "org.gnome.SessionManager"
SM_PATH = "/org/gnome/SessionManager"
SM_IFACE = "org.gnome.SessionManager"
INHIBIT_IDLE = 8

SS_BUS = "org.gnome.ScreenSaver"
SS_PATH = "/org/gnome/ScreenSaver"
SS_IFACE = "org.gnome.ScreenSaver"

PLAYER = os.path.join(os.path.dirname(os.path.realpath(__file__)), "player.py")


def log(*a):
    print("[aerial-daemon]", *a, flush=True)


class Daemon:
    def __init__(self):
        self.loop = GLib.MainLoop()
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.cfg = cfgmod.load()
        self.watch_id = None
        self.proc = None
        self._reload_src = None
        self._retry_src = None

        Gio.bus_watch_name_on_connection(
            self.bus, IDLE_BUS, Gio.BusNameWatcherFlags.NONE,
            self._on_mutter_appeared, self._on_mutter_vanished)

        self.bus.signal_subscribe(
            IDLE_BUS, IDLE_IFACE, "WatchFired", IDLE_PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_watch_fired)

        self.bus.signal_subscribe(
            SS_BUS, SS_IFACE, "ActiveChanged", SS_PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_lock_changed)

        os.makedirs(cfgmod.CONFIG_DIR, exist_ok=True)
        self.monitor = Gio.File.new_for_path(cfgmod.CONFIG_DIR).monitor_directory(
            Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self._on_config_changed)

        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            unix_signal_add(sig, self._on_signal, sig)

    def _call(self, name, path, iface, method, args=None, timeout=2000):
        try:
            return self.bus.call_sync(name, path, iface, method, args, None,
                                      Gio.DBusCallFlags.NONE, timeout, None)
        except GLib.Error as e:
            log(f"{iface}.{method} başarısız: {e.message}")
            return None

    def _is_locked(self):
        r = self._call(SS_BUS, SS_PATH, SS_IFACE, "GetActive")
        return bool(r and r.unpack()[0])

    def _is_inhibited(self):
        r = self._call(SM_BUS, SM_PATH, SM_IFACE, "IsInhibited",
                       GLib.Variant("(u)", (INHIBIT_IDLE,)))
        return bool(r and r.unpack()[0])

    def _remove_watch(self):
        if self.watch_id is not None:
            self._call(IDLE_BUS, IDLE_PATH, IDLE_IFACE, "RemoveWatch",
                       GLib.Variant("(u)", (self.watch_id,)))
            self.watch_id = None

    def _add_watch(self):
        self._remove_watch()
        if not self.cfg.enabled:
            log("devre dışı (ayarlardan etkinleştirilebilir)")
            return
        ms = int(self.cfg.idle_minutes * 60 * 1000)
        r = self._call(IDLE_BUS, IDLE_PATH, IDLE_IFACE, "AddIdleWatch",
                       GLib.Variant("(t)", (ms,)))
        if r is not None:
            self.watch_id = r.unpack()[0]
            log(f"boşta izleme kuruldu: {self.cfg.idle_minutes:g} dk (id={self.watch_id})")

    def _on_mutter_appeared(self, *_):
        self.watch_id = None
        self._add_watch()

    def _on_mutter_vanished(self, *_):
        self.watch_id = None

    def _on_watch_fired(self, _conn, _sender, _path, _iface, _sig, params):
        (wid,) = params.unpack()
        if wid != self.watch_id:
            return
        self._try_start()

    def _try_start(self):
        if self.proc is not None or not self.cfg.enabled:
            return False
        if self._is_locked():
            log("ekran kilitli, atlanıyor")
            return False
        if self.cfg.respect_inhibit and self._is_inhibited():
            log("boşta kalma engellenmiş (video/sunum), 30 sn sonra tekrar denenecek")
            if self._retry_src is None:
                self._retry_src = GLib.timeout_add_seconds(30, self._retry)
            return True
        self._start_player()
        return False

    def _retry(self):
        r = self._call(IDLE_BUS, IDLE_PATH, IDLE_IFACE, "GetIdletime")
        idle_ms = r.unpack()[0] if r else 0
        if idle_ms < self.cfg.idle_minutes * 60 * 1000:
            self._retry_src = None
            return GLib.SOURCE_REMOVE
        self._retry_src = None
        self._try_start()
        return GLib.SOURCE_REMOVE

    def _start_player(self):
        try:
            self.proc = Gio.Subprocess.new([sys.executable, PLAYER],
                                           Gio.SubprocessFlags.NONE)
        except GLib.Error as e:
            log("oynatıcı başlatılamadı:", e.message)
            self.proc = None
            return
        log("oynatıcı başlatıldı")
        self.proc.wait_async(None, self._on_player_exit, self.proc)

    def _on_player_exit(self, proc, result, data):
        try:
            proc.wait_finish(result)
        except GLib.Error:
            pass
        if self.proc is data:
            self.proc = None
        log("oynatıcı kapandı")

    def _stop_player(self):
        if self.proc is not None:
            self.proc.send_signal(signal.SIGTERM)

    def _on_lock_changed(self, _c, _s, _p, _i, _sig, params):
        (active,) = params.unpack()
        if active:
            log("ekran kilitlendi, oynatıcı kapatılıyor")
            self._stop_player()

    def _on_config_changed(self, _mon, file, _other, event):
        if file.get_path() != cfgmod.CONFIG_PATH:
            return
        if event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT,
                         Gio.FileMonitorEvent.CREATED,
                         Gio.FileMonitorEvent.MOVED_IN,
                         Gio.FileMonitorEvent.RENAMED,
                         Gio.FileMonitorEvent.DELETED):
            return
        if self._reload_src is None:
            self._reload_src = GLib.timeout_add(300, self._reload)

    def _reload(self):
        self._reload_src = None
        new = cfgmod.load()
        changed = (new.enabled, new.idle_minutes) != (self.cfg.enabled, self.cfg.idle_minutes)
        self.cfg = new
        log("ayarlar yeniden yüklendi")
        if changed:
            self._add_watch()
        return GLib.SOURCE_REMOVE

    def _on_signal(self, _sig):
        self._stop_player()
        self._remove_watch()
        self.loop.quit()
        return GLib.SOURCE_REMOVE

    def run(self):
        self.loop.run()


def main():
    try:
        Daemon().run()
    except GLib.Error as e:
        log("D-Bus bağlantı hatası:", e.message)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
