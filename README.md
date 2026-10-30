# Aerial Views for Linux (GNOME / Wayland)

macOS ve Apple TV'deki meşhur **Aerial Views** canlı video ekran koruyucusunun Linux Wayland sürümü.

Apple'ın yüksek kaliteli (1080p / 4K) orijinal hava çekimlerini (Dubai, San Francisco, New York, Hawaii, Uzay / ISS, Mercan Resifleri vb.) Wayland masaüstünde ekran kartı donanım hızlandırmasıyla (`mpv --hwdec=auto`) akıcı ve sıfır işlemci yüküyle oynatır.

## Özellikler

- **Orijinal Apple Video Akışları:** 60+ farklı konum ve yüzlerce çekim.
- **Akıllı Donanım Hızlandırma:** `mpv` Wayland motoru sayesinde %1-2 CPU kullanımı, sıfır ısınma.
- **macOS Tarzı Bilgi Katmanı (Overlay):**
  - Sol alt köşe: Şehir ve manzara açıklaması (Türkçe veya İngilizce).
  - Sağ alt köşe: Zarif minimal dijital saat ve tarih.
- **Gündüz / Gece Uyumu:** Gündüzleri güneşli çekimler, geceleri şehir ışıkları otomatik seçilir.
- **Akıllı Önbellek (Smart Cache):** İzlenen videoları arka planda yerel diske kaydeder; bir sonraki oynatmada internet harcamadan çevrimdışı oynatır.
- **Wayland Güvenliği ve Kilit:**
  - Fareyi oynatınca veya bir tuşa basınca anında kapanır.
  - İsteğe bağlı olarak kapanırken masaüstü görünmeden GNOME oturumunu kilitler (`lock_on_exit`).
  - Video veya film izlerken (`SessionManager.IsInhibited`) devreye girmez.
- **libadwaita / GTK4 Ayar Arayüzü:** Tüm ayarları kolayca değiştirebilirsiniz.

## Kurulum

```bash
./install.sh
```
`sudo` gerektirmez. Dosyalar `~/.local` ve `~/.config` altına kurulur.

## Kullanım

- **Uygulamalar Menüsü:**
  - *Aerial Views* (Canlı ekran koruyucuyu hemen başlat)
  - *Aerial Views Ayarları* (Kalite, süre, saat, önbellek ayarları)
- **Terminal Komutları:**
  - `aerial-views` (Tam ekran başlat)
  - `aerial-views --preview` (Pencere modunda önizle)
  - `aerial-settings` (Ayar penceresini aç)
- **Canlı Günlük:**
  - `journalctl --user -u aerial-daemon -f`

## Kaldırma

```bash
./uninstall.sh
```
