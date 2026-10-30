"""Video listesi, önbellek ve oynatma kuyruğu yönetimi."""

import json
import os
import random
import time
from typing import Dict, List, Optional
from aerial_linux import config as cfgmod

DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "videos.json")


def load_videos() -> List[Dict]:
    """Paketteki Apple Aerial video listesini yükler."""
    if not os.path.exists(DATA_PATH):
        return []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[aerial] Video veritabanı okunamadı: {e}")
        return []


def get_video_url(item: Dict, quality: str) -> str:
    """Seçilen kaliteye göre en uygun Apple CDN URL'sini döner."""
    if quality == "4k-hevc":
        return item.get("url_4k_hevc") or item.get("url_1080_hevc") or item.get("url_1080_h264") or ""
    elif quality == "1080p-hevc":
        return item.get("url_1080_hevc") or item.get("url_1080_h264") or item.get("url_4k_hevc") or ""
    else:  # "1080p-h264" (en hızlı, en uyumlu)
        return item.get("url_1080_h264") or item.get("url_1080_hevc") or item.get("url_4k_hevc") or ""


def get_cached_path(item: Dict, quality: str) -> Optional[str]:
    """Eğer video yerel önbelleğe indirilmişse yolunu döner, yoksa None."""
    vid_id = item.get("id") or "vid"
    ext = ".mov"
    filename = f"{vid_id}_{quality}{ext}"
    path = os.path.join(cfgmod.CACHE_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > 1024 * 1024:
        return path
    return None


def get_playlist(cfg: cfgmod.Config) -> List[Dict]:
    """Ayarlara göre filtrelenmiş ve karıştırılmış oynatma listesi döner."""
    videos = load_videos()
    if not videos:
        return []

    # Gündüz / Gece uyumu
    if cfg.time_sync:
        cur_hour = time.localtime().tm_hour
        is_day = 6 <= cur_hour < 19
        target = "day" if is_day else "night"
        filtered = [v for v in videos if v.get("timeOfDay") == target]
        if len(filtered) >= 5:
            videos = filtered

    random.shuffle(videos)

    playlist = []
    for item in videos:
        # Önce önbellek kontrolü
        local_file = get_cached_path(item, cfg.quality)
        stream_url = get_video_url(item, cfg.quality)

        title = item.get(f"title_{cfg.language}") or item.get("title_tr") or item.get("location") or "Manzara"
        subtitle = item.get(f"subtitle_{cfg.language}") or item.get("subtitle_tr") or ""

        entry = {
            "id": item.get("id"),
            "location": item.get("location"),
            "title": title,
            "subtitle": subtitle,
            "stream_url": stream_url,
            "play_path": local_file if local_file else stream_url,
            "is_cached": bool(local_file),
            "quality": cfg.quality
        }
        if entry["play_path"]:
            playlist.append(entry)

    return playlist
