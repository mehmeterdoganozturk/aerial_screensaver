# Aerial Views for Linux (GNOME / Wayland) ✈️🌍
**Apple TV & macOS Canlı Hava Çekimleri Ekran Koruyucusu (Ubuntu 24.04 / 26.04 Wayland Uyumlu)**

macOS ve Apple TV'deki meşhur **Aerial Views** canlı video ekran koruyucusunun Linux Wayland ortamı için özel olarak geliştirilmiş yüksek performanslı sürümüdür.

Apple'ın resmi 1080p ve 4K HDR hava çekimlerini (Dubai, San Francisco, New York, Hawaii, Uzay / Uluslararası Uzay İstasyonu, Grönland, Mercan Resifleri vb.) Wayland masaüstünde ekran kartı donanım hızlandırmasıyla (`mpv --hwdec=auto`) **akıcı 60 FPS ve %1-2 işlemci yüküyle** tam ekran oynatır.

---

## 📑 İçindekiler
- [✨ Öne Çıkan Özellikler](#-öne-çıkan-özellikler)
- [🏗️ Nasıl Çalışır? (Teknik Mimari)](#️-nasıl-çalışır-teknik-mimari)
- [🖥️ Ekran Bilgi Katmanı (macOS Tarzı Overlay)](#️-ekran-bilgi-katmanı-macos-tarzı-overlay)
- [🚀 Kurulum ve İlk Çalıştırma](#-kurulum-ve-ilk-çalıştırma)
- [🎮 Kullanım & Terminal Komutları](#-kullanım--terminal-komutları)
- [⚙️ Ayarlar & Yapılandırma](#️-ayarlar--yapılandırma)
- [💾 Akıllı Önbellek Sistemi (Smart Caching)](#-akıllı-önbellek-sistemi-smart-caching)
- [🔒 Güvenlik & Ekran Kilidi Entegrasyonu](#-güvenlik--ekran-kilidi-entegrasyonu)
- [📂 Proje Dizin Yapısı](#-proje-dizin-yapısı)
- [🗑️ Kaldırma](#️-kaldırma)
- [📜 Lisans & Telif Hakkı](#-lisans--telif-hakkı)

---

## ✨ Öne Çıkan Özellikler

1. **Orijinal Apple Video Arşivi**:
   * Apple'ın doğrudan CDN sunucularından çekilen 60+ farklı coğrafi konum ve yüzlerce yüksek çözünürlüklü video akışı.
   * Gündüz / Gece Uyumu: Gündüz saatlerinde güneşli manzaralar, gece saatlerinde şehir ışıkları ve uzay manzaraları otomatik seçilir.
2. **Akıllı Donanım Hızlandırma (`mpv`)**:
   * `VA-API` / `NVDEC` donanım kod çözücü entegrasyonu sayesinde CPU kullanımı %1-2 civarındadır; bilgisayarınız ısınmaz ve fan sesi yapmaz.
   * Çift ve çoklu monitör desteği (her ekranda kusursuz tam ekran).
3. **Akıllı Önbellek (Smart Cache)**:
   * İlk kez izlenen videolar arka planda yerel diskinize kaydedilir. Sonraki oynatmalarda internet kotası harcanmaz, çevrimdışı oynatılır.
4. **Masaüstü ve Medya Duyarlılığı**:
   * Video izlerken (YouTube, VLC vb.), oyun oynarken veya sunum yaparken (`org.gnome.SessionManager.IsInhibited`) ekran koruyucu devreye girmez.
   * Fare kıpırdadığı veya klavyede herhangi bir tuşa basıldığı anda 0.05 saniyede akıcı biçimde kapanır.
5. **Modern Libadwaita / GTK4 Ayar Arayüzü**:
   * Video kalitesi (1080p / 4K), boşta kalma süresi, saat/tarih görünürlüğü ve konum filtreleri grafik arayüzden kolayca yönetilebilir.

---

## 🏗️ Nasıl Çalışır? (Teknik Mimari)

GNOME Wayland oturumlarında X11'deki gibi güvensiz XScreenSaver modülleri çalışmaz. Bu proje şu modern Wayland mimarisini kullanır:

```
+--------------------------------------------------------------+
|                     GNOME Mutter (Wayland)                   |
|          D-Bus: org.gnome.Mutter.IdleMonitor                 |
+------------------------------▲-------------------------------+
                               │ Boşta kalma süresi izleme
                               ▼
+--------------------------------------------------------------+
|                  Aerial Daemon (systemd --user)              |
|                     (aerial-linux/daemon.py)                 |
|                                                              |
|  * Video oynatıcılar (Inhibit) kontrolü                      |
|  * Oturum kilitli mi kontrolü                                |
|  * Boşta kalma süresi dolunca mpv motorunu tetikler          |
+------------------------------▲-------------------------------+
                               │
                               ▼
+--------------------------------------------------------------+
|                    MPV Wayland Oynatıcı                      |
|                                                              |
|  * Donanım Hızlandırma: --hwdec=auto (VA-API / NVDEC)        |
|  * Özel Lua Overlay (overlay.lua): Konum adı + Saat          |
|  * Apple Video CDN Stream + Yerel Akıllı Önbellek            |
+--------------------------------------------------------------+
```

---

## 🖥️ Ekran Bilgi Katmanı (macOS Tarzı Overlay)

Özel `overlay.lua` katmanı, video oynatılırken ekranın köşelerine zarif animasyonlu bilgiler ekler:
* **Sol Alt Köşe**: Manzaranın adı, şehri ve çekim detayları (Örn: *Hawaii - Na Pali Kıyısı*, *Dubai Gece Işıkları*).
* **Sağ Alt Köşe**: Canlı dijital saat ve tarih (Örn: *21:45 • Perşembe, 29 Ekim*).
* **Görünürlük Ayarı**: İsteğe bağlı olarak sadece saat, sadece konum veya tamamen temiz ekran seçilebilir.

---

## 🚀 Kurulum ve İlk Çalıştırma

Sisteminize root (`sudo`) yetkisi gerekmeden tek komutla kurabilirsiniz:

```bash
git clone https://github.com/mehmeterdoganozturk/aerial_screensaver.git
cd aerial_screensaver
chmod +x install.sh
./install.sh
```

**Kurulum Betiği Neler Yapar?**
1. Gerekli Python ve GTK dosyalarını `~/.local/share/aerial-screensaver/` dizinine kopyalar.
2. Terminal komutlarını (`aerial-views`, `aerial-settings`) `~/.local/bin` altına ekler.
3. Arka plan servis dosyasını `~/.config/systemd/user/aerial-daemon.service` olarak kaydeder ve otomatik başlatır.
4. Masaüstü menüsüne *Aerial Views* ve *Aerial Views Ayarları* kısayollarını ekler.

---

## 🎮 Kullanım & Terminal Komutları

* **Uygulamayı Hemen Başlat**:
  ```bash
  aerial-views
  ```
* **Pencere Modunda Önizleme**:
  ```bash
  aerial-views --preview
  ```
* **Ayar Panelini Aç**:
  ```bash
  aerial-settings
  ```
* **Arka Plan Servis Durumunu Kontrol Et**:
  ```bash
  systemctl --user status aerial-daemon
  ```
* **Canlı Log İzleme**:
  ```bash
  journalctl --user -u aerial-daemon -f
  ```

---

## ⚙️ Ayarlar & Yapılandırma

Ayarlar penceresini (`aerial-settings`) kullanarak veya `~/.config/aerial-screensaver/config.json` dosyasını düzenleyerek şu özellikleri değiştirebilirsiniz:

| Parametre | Açıklama | Varsayılan |
|---|---|---|
| `idle_minutes` | Ekran koruyucunun devreye gireceği boşta kalma süresi (dakika) | `5` |
| `quality` | Video kalitesi (`"1080p"` veya `"4k"`) | `"1080p"` |
| `time_of_day_filter` | Gündüz/gece saatine göre video seçimi (`true`/`false`) | `true` |
| `show_location` | Sol altta manzara adını gösterme (`true`/`false`) | `true` |
| `show_clock` | Sağ altta saat ve tarihi gösterme (`true`/`false`) | `true` |
| `lock_on_exit` | Ekran koruyucu kapatıldığında masaüstünü kilitleme | `false` |
| `cache_videos` | İzlenen videoları otomatik diske kaydetme | `true` |

---

## 💾 Akıllı Önbellek Sistemi (Smart Caching)

Videolar `~/.cache/aerial-screensaver/videos/` klasöründe saklanır.
* İndirilen videolar isimleri ve konum bilgileriyle etiketlenir.
* Çevrimdışı kaldığınızda sistem internet aramaz, daha önce indirilmiş yerel videolardan rastgele oynatmaya devam eder.
* İstediğiniz zaman ayarlar panelinden önbelleği temizleyebilir veya disk sınırını belirleyebilirsiniz.

---

## 🔒 Güvenlik & Ekran Kilidi Entegrasyonu

* **Oturum Kilidi Koruması**: Bilgisayar kilitlendiğinde (`Super + L` veya otomatik kilit) arka planda video oynatımı hemen durdurulur ve kaynaklar serbest bırakılır.
* **Kapanışta Kilitleme (`lock_on_exit`)**: Bu ayar aktif edildiğinde, bilgisayarınızın başına dönüp fareyi hareket ettirdiğinizde video kapanır ve doğrudan GNOME parola giriş ekranı karşılar.

---

## 📂 Proje Dizin Yapısı

```
aerial_screensaver/
├── LICENSE                        # Resmi MIT Lisans belgesi
├── README.md                      # Detaylı kullanım ve kurulum kılavuzu
├── install.sh                     # Otomatik kurulum ve systemd yapılandırma betiği
├── uninstall.sh                   # Temiz kaldırma betiği
├── data/                          # Masaüstü .desktop dosyaları ve ikonlar
└── aerial_linux/                  # Çekirdek Python paketi
    ├── daemon.py                  # Mutter IdleMonitor boşta kalma servisi
    ├── player.py                  # mpv Wayland oynatıcı yöneticisi
    ├── manifest.py                # Apple CDN video kataloğu indirici ve ayrıştırıcı
    ├── overlay.lua                # mpv için OSD bilgi katmanı (Saat + Konum)
    ├── settings.py                # Libadwaita / GTK4 grafik ayar arayüzü
    ├── config.py                  # JSON yapılandırma yöneticisi
    └── auth.py                    # Ekran kilidi ve oturum doğrulama modülü
```

---

## 🗑️ Kaldırma

Sistemden ve servislerden tamamen kaldırmak için:

```bash
cd /home/erdogan/Projects/aerial_screensaver
./uninstall.sh
```

---

## 📜 Lisans & Telif Hakkı

Bu proje [MIT Lisansı](LICENSE) altında açık kaynak olarak sunulmuştur.  
© 2026 **Mehmet Erdoğan Öztürk** <mehmeterdoganozturk@gmail.com>
