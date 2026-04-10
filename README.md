# Günlük Hal Fiyatları Scraper Projesi

Bu proje, İstanbul Büyükşehir Belediyesi ve Harmanapps web sitelerinden günlük sebze ve meyve hal fiyatlarını otomatik olarak çekmek (scrape etmek) için tasarlanmış iki ayrı Python betiğini içerir.

## Proje Yapısı

### 1. `Istanbul_Hal`
Bu klasörde İBB Hal Kayıt Sisteminden verileri otomatik çeken script yer alır.
- **`ist_gunluk_hal_fiyat_scraber.py`**: Selenium kütüphanesini kullanarak `tarim.ibb.istanbul` adresine bağlanır. Arka planda Chrome'u çalıştırarak (headless mod) "Meyve", "Sebze" ve "İthal Ürünler" kategorilerini seçer, gelen tablo değerlerini ayrıştırır.
- **Çıktı**: `istanbul_hal_fiyat_gg_aa_yyyy.csv` (Örn: `istanbul_hal_fiyat_10_04_2026.csv`). Veriler oluşturulduğu günün tarihi ile kaydedilir. İçerisinde Kategori, Ürün Adı, Birim, En Düşük Fiyat, En Yüksek Fiyat ve Tarih sütunları yer alır.

### 2. `Harman_Hal`
Bu klasörde, Cloudflare güvenlik sistemine sahip olan `harmanapps.com` sitesinden verileri hızlıca çeken script bulunur.
- **`harman_gunluk_hal_fiyat_scraber.py`**: Selenium (tarayıcı) kullanmak yerine hız ve Cloudflare atlatabilmesi için `curl_cffi` kütüphanesini kullanır. Tüm şehir linklerini analiz edip ilgili sayfalardan veriyi ayrıştırır. Pagination (sayfalama) mantığını otomatik olarak izler.
- **Çıktı**: `harman_hal_fiyat_gg_aa_yyyy.csv` (Örn: `harman_hal_fiyat_10_04_2026.csv`). Veriler içerisinde Şehir, Ürün, Konum, En Düşük, En Yüksek ve Tarih sütunları bulunur.

## Kurulum ve Gereksinimler

Projeyi çalıştırmadan önce aşağıdaki kütüphanelerin Python (veya Anaconda) ortamınıza kurulu olduğundan emin olun:

```bash
# İstanbul Hal Scraper için gerekenler:
pip install pandas selenium

# Harmanapps Hal Scraper için gerekenler:
pip install pandas curl_cffi beautifulsoup4
```

## Nasıl Çalıştırılır?

Her iki script de bağlı bulundukları klasör dizini gözetilmeksizin terminal üzerinden çalıştırılabilir. Verilen csv çıktısı çalıştırıldığı klasöre çıkartılır.

**İstanbul Hal Kodu:**
```bash
cd Istanbul_Hal
python ist_gunluk_hal_fiyat_scraber.py
```

**Harmanapps Kodu:**
```bash
cd Harman_Hal
python harman_gunluk_hal_fiyat_scraber.py
```

## Notlar
- Selenium betiği (İstanbul) çalışırken Chrome'a ihtiyaç duyar, gizli (`headless`) çalışır. Sisteminizde Chrome'un bir versiyonu yüklü olmalıdır.
- Harmanapps betiğinde (`curl_cffi` ile) Chrome açılmaz, TLS fingerprinting ile doğrudan istek atılarak işlem saniyeler içerisinde tamamlanır.
