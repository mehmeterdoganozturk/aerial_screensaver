"""Ortak ayar dosyası yönetimi: ~/.config/aerial-linux/config.ini"""

import configparser
import os
from dataclasses import dataclass, asdict, fields

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "aerial-linux",
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.ini")

CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
    "aerial-linux",
    "videos",
)


@dataclass
class Config:
    # Video & Kalite
    # Seçenekler: "1080p-h264", "1080p-hevc", "4k-hevc"
    quality: str = "1080p-h264"
    time_sync: bool = True           # Gündüz vakti gündüz, gece vakti gece çekimleri
    language: str = "tr"             # "tr" veya "en"

    # Ekran üstü bilgiler (Overlay)
    show_location: bool = False       # Sol alt köşe: Konum başlığı ve açıklaması
    show_clock: bool = True          # Sağ alt köşe: Minimal dijital saat & tarih
    clock_24h: bool = True           # 24 saat biçimi

    # Önbellek & Ağ
    cache_enabled: bool = True       # İzlenen videoları diske kaydet (sonrakinde çevrimdışı çalar)
    cache_limit_gb: float = 5.0      # Maksimum önbellek sınırı (GB)

    # Ekran koruyucu servisi
    enabled: bool = True             # Boşta kalınca otomatik başlama
    idle_minutes: float = 5.0        # Boşta kalma süresi (dakika)
    respect_inhibit: bool = True     # Video vb. oynarken başlatma
    lock_on_exit: bool = True        # Çıkarken ekranı kilitle
    lock_mode: str = "macos"         # "macos" (entegre kilit kartı & geri çekilme) veya "gnome"
    lock_timeout: int = 20           # macOS kilit ekranı zaman aşımı (saniye)
    all_monitors: bool = True        # Tüm monitörlerde göster

    def clamp(self) -> "Config":
        self.idle_minutes = min(240.0, max(0.25, float(self.idle_minutes)))
        self.cache_limit_gb = min(50.0, max(0.5, float(self.cache_limit_gb)))
        if self.quality not in ("1080p-h264", "1080p-hevc", "4k-hevc"):
            self.quality = "1080p-h264"
        if self.language not in ("tr", "en"):
            self.language = "tr"
        if self.lock_mode not in ("macos", "gnome"):
            self.lock_mode = "macos"
        try:
            self.lock_timeout = min(120, max(5, int(self.lock_timeout)))
        except (ValueError, TypeError):
            self.lock_timeout = 20
        return self


def _to_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on", "evet")


def load() -> Config:
    cfg = Config()
    parser = configparser.ConfigParser()
    try:
        parser.read(CONFIG_PATH, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return cfg.clamp()

    if not parser.has_section("aerial"):
        return cfg.clamp()

    sec = parser["aerial"]
    for f in fields(Config):
        if f.name not in sec:
            continue
        raw = sec[f.name]
        try:
            if f.type in (bool, "bool"):
                setattr(cfg, f.name, _to_bool(raw))
            elif f.type in (float, "float"):
                setattr(cfg, f.name, float(raw))
            elif f.type in (int, "int"):
                setattr(cfg, f.name, int(raw))
            else:
                setattr(cfg, f.name, str(raw))
        except ValueError:
            pass
    return cfg.clamp()


def save(cfg: Config) -> None:
    cfg.clamp()
    os.makedirs(CONFIG_DIR, exist_ok=True)
    parser = configparser.ConfigParser()
    parser["aerial"] = {k: str(v) for k, v in asdict(cfg).items()}
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        parser.write(fh)
    os.replace(tmp, CONFIG_PATH)
