#!/usr/bin/env bash
# Aerial Views for Linux (GNOME/Wayland) — Kullanıcı düzeyinde kurulum (sudo gerekmez)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/aerial-linux"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> Bağımlılıklar kontrol ediliyor"
missing=()
which mpv >/dev/null 2>&1 || missing+=(mpv)
python3 -c 'import gi; gi.require_version("Gtk","4.0"); from gi.repository import Gtk' 2>/dev/null || missing+=(gir1.2-gtk-4.0 python3-gi)
python3 -c 'import gi; gi.require_version("Adw","1"); from gi.repository import Adw' 2>/dev/null || missing+=(gir1.2-adw-1)

if ((${#missing[@]})); then
    echo "Eksik paketler: ${missing[*]}"
    echo "Kurmak için:  sudo apt install ${missing[*]}"
    exit 1
fi

echo "==> Dosyalar kopyalanıyor: $DEST"
rm -rf "$DEST"
mkdir -p "$DEST" "$BIN" "$APPS" "$ICONS" "$UNITS"
cp -r "$SRC/aerial_linux" "$DEST/"
find "$DEST" -name '__pycache__' -prune -exec rm -rf {} +
chmod +x "$DEST/aerial_linux/"{player,daemon,settings}.py
cp "$SRC/data/aerial-views.svg" "$ICONS/aerial-views.svg"

ln -sf "$DEST/aerial_linux/player.py"   "$BIN/aerial-views"
ln -sf "$DEST/aerial_linux/settings.py" "$BIN/aerial-settings"

sed "s|@DEST@|$DEST|g" "$SRC/data/aerial-views.desktop.in"    > "$APPS/aerial-views.desktop"
sed "s|@DEST@|$DEST|g" "$SRC/data/aerial-settings.desktop.in" > "$APPS/aerial-settings.desktop"
sed "s|@DEST@|$DEST|g" "$SRC/data/aerial-daemon.service.in"  > "$UNITS/aerial-daemon.service"

update-desktop-database "$APPS" >/dev/null 2>&1 || true
gtk-update-icon-cache -q "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "==> Servis etkinleştiriliyor"
systemctl --user daemon-reload
systemctl --user enable aerial-daemon.service >/dev/null 2>&1 || true
systemctl --user restart aerial-daemon.service || true
sleep 1
systemctl --user --no-pager --lines=5 status aerial-daemon.service || true

echo
echo "Kurulum tamamlandı!"
echo "  • Uygulamalar menüsü: 'Aerial Views' ve 'Aerial Views Ayarları'"
echo "  • Terminal komutları: aerial-views  |  aerial-views --preview  |  aerial-settings"
echo "  • Canlı günlük:      journalctl --user -u aerial-daemon -f"
