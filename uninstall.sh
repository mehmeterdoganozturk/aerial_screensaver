#!/usr/bin/env bash
# Aerial Views for Linux kaldırma scripti
set -u
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
systemctl --user disable --now aerial-daemon.service 2>/dev/null || true
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/aerial-daemon.service"
systemctl --user daemon-reload 2>/dev/null || true
rm -rf "$DATA/aerial-linux"
rm -f "$HOME/.local/bin/aerial-views" "$HOME/.local/bin/aerial-settings"
rm -f "$DATA/applications/aerial-views.desktop" "$DATA/applications/aerial-settings.desktop"
rm -f "$DATA/icons/hicolor/scalable/apps/aerial-views.svg"
update-desktop-database "$DATA/applications" >/dev/null 2>&1 || true
echo "Aerial Views kaldırıldı. (Önbellek ve ayarlar korundu: ~/.config/aerial-linux ~/.cache/aerial-linux)"
