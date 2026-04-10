# Türkiye Gıda Tedarik Zinciri Şeffaflık Motoru
## Hal→Market İl Bazlı Marj Analizi ve Fiyat Propagasyon Data Engineering Platformu

### Master Tez / Proje Raporu — Detaylı Tasarım Dokümanı

---

## 1. Proje Başlığı

**GıdaRadar Turkey: Toptancı Hal → Perakende Market Tedarik Zinciri Marj Analizi, İl Bazlı Fiyat Farklılık Tespiti ve Şok Propagasyon Platformu**

---

## 2. Yönetici Özeti

Bu proje, Türkiye'nin gıda tedarik zincirindeki **hiç ölçülmemiş** bir boşluğu dolduruyor: toptancı hal giriş fiyatları ile perakende market raf fiyatları arasındaki marjın ürün bazında, market bazında ve il bazında sistematik olarak izlenmesi.

Projenin benzersiz veri avantajı şudur: 2025 yılında Türkiye'de iki kritik veri kaynağı aynı anda erişilebilir hale gelmiştir. Birincisi, TÜBİTAK BİLGEM tarafından geliştirilen marketfiyati.org.tr platformu 7 zincir marketten 50.000 ürünün mağaza ve konum bazlı perakende fiyatlarını günlük olarak sunmaktadır. İkincisi, İBB ve İzmir BB açık veri portalleri toptancı hal giriş fiyatlarını (min/max/ortalama) ve aylık tonaj verilerini Swagger API ve CSV olarak tarihsel derinlikle paylaşmaktadır. Bu iki katmanı birleştirmek, GDELT haber verileri, Open-Meteo hava durumu verileri, EPİAŞ enerji maliyetleri ve TCMB makroekonomik göstergelerle zenginleştirmek dünyanın nadir bulunur açık veri fırsatlarından biridir.

Proje, 8 farklı veri kaynağından 5 farklı formatta (HTML, JSON, CSV, TSV, XML) veri toplayarak uçtan uca bir streaming + batch data engineering pipeline'ı inşa eder. Machine learning yalnızca destekleyici rol oynar (entity resolution, anomali tespiti); asıl katkı veri entegrasyonu, temporal alignment ve il bazlı geospatial analiz mimarisidir.

---

## 3. Business Problemi

### 3.1. Ana Problem: Tedarik Zinciri Marj Opakliği

Türkiye'de bir domates İstanbul Bayrampaşa Hal'ine 8 TL/kg toptan fiyatla girerken, aynı domates markette 22-30 TL/kg'dan satılmaktadır. Bu aradaki fark (marj) nakliye, depolama, fire, market kârı ve çeşitli aracı maliyetlerini içerir. Ancak bu marjın ne kadar olduğu, ürünler ve marketler arasında nasıl farklılaştığı, mevsimsel olarak nasıl değiştiği ve iller arasında nasıl farklılık gösterdiği sistematik olarak hiç ölçülmemiştir.

### 3.2. Çözülecek Karar Problemleri

**Problem 1 — İl Bazlı Fiyat Eşitsizlik Haritası:** Aynı ürünün (örn: 1 kg kıyma, 1 lt süt, 1 kg domates) İstanbul Kadıköy'deki Migros'ta, Ankara Çankaya'daki BİM'de ve İzmir Bornova'daki A101'de ne kadara satıldığı — ve bu farkların sistematik mi yoksa rastgele mi olduğu. marketfiyati.org.tr'nin konum bazlı fiyat verisi bu analizi il, ilçe ve hatta mağaza düzeyinde mümkün kılmaktadır. Bigpara'nın haberinde İstanbul Eyüpsultan'da aynı markalı 1 litre zeytinyağının üç markette sırasıyla 184.50 TL, 278.60 TL ve 303.95 TL'ye satıldığı — yani yüzde 64.7 fiyat farkı — belgelenmiştir.

**Problem 2 — Hal→Market Marj Analizi:** İBB hal fiyatları (toptan giriş) ile marketfiyati.org.tr fiyatları (perakende satış) arasındaki farkı ürün bazında, günlük olarak, 7 market için ayrı ayrı ölçmek. Hangi ürünlerde marj en yüksek? Marj mevsimsel mi, yapısal mı? Hangi marketler daha düşük marjla çalışıyor?

**Problem 3 — Hava Durumu → Arz Şoku → Fiyat Yayılım Hızı:** Open-Meteo'dan Antalya'da don olayı tespit edildiğinde, bu şok İBB Hal fiyatına kaç günde yansıyor, oradan markete kaç günde geçiyor? Bu "şok propagasyon hızı" ölçümü lojistik verimliliğin gerçek göstergesidir.

**Problem 4 — Asimetrik Fiyat Geçişkenliği (Rockets and Feathers):** Hal fiyatı düştüğünde market fiyatı ne kadar gecikmeli düşüyor (feathers/tüy — yavaş iniş) vs. hal fiyatı arttığında market fiyatı ne kadar hızlı artıyor (rockets/roket — hızlı çıkış)? Bu asimetri 7 market arasında farklı mı?

**Problem 5 — Enerji Maliyeti → Soğuk Zincir Ürün Fiyatı Transmisyonu:** EPİAŞ elektrik fiyatları ve TCMB doğalgaz fiyatlarının soğuk zincir ürünlerine (süt, et, dondurulmuş gıda) ne hızda aktarıldığını izleyen koridor analizi.

**Problem 6 — GDELT Haber Etkisi Ölçümü:** "Domates fiyatları uçtu" haberi çıktığında hal fiyatları gerçekten yüksek mi, yoksa medya spekülatif mi? Haber tonu → tüketici davranış değişikliği → fiyat döngüsü sistematik olarak var mı?

### 3.3. Karar Destek Çıktıları

Bu platform şu aktörler için doğrudan karar destek sistemi üretir: Rekabet Kurumu (market oligopol davranışı tespiti), Ticaret Bakanlığı Haksız Fiyat Değerlendirme Kurulu (fahiş fiyat artışı tespiti), TCMB (gıda enflasyonu bileşen analizi), tarım politikası yapıcıları (arz-talep dengesizlik erken uyarı), zincir market yönetimleri (rekabetçi fiyatlama stratejisi) ve tüketici dernekleri (fiyat şeffaflığı raporlaması).

---

## 4. Türkiye ile Bağlantısı

Türkiye bu proje için dünyada benzersiz koşullar sunmaktadır. Birincisi, marketfiyati.org.tr dünyanın sayılı devlet destekli, 50.000 ürünlük, 7 marketlik, konum bazlı, günlük güncellenen perakende fiyat platformlarından biridir. İkincisi, İBB ve İzmir BB hal API'leri toptancı giriş fiyatlarını açık veri olarak sunan nadir belediyeler arasındadır. Üçüncüsü, Türkiye'nin yüksek enflasyon ortamı fiyat geçişkenlik analizini hem akademik hem politik açıdan son derece anlamlı kılmaktadır. Dördüncüsü, Türk perakende sektörünün yapısı (discount BİM/A101/ŞOK + full-service Migros/CarrefourSA + kamu Tarım Kredi) karşılaştırmalı analiz için ideal bir doğal deney ortamı yaratmaktadır. Beşincisi, coğrafi çeşitlilik (Akdeniz tarım bölgesi → Marmara tüketim merkezi → İç Anadolu karasal iklim) arz şoklarının mekansal yayılımını incelemeye olanak tanımaktadır.

---

## 5. Kullanılabilecek Veri Kaynakları (8 Farklı Kaynak)

### 5.1. marketfiyati.org.tr — Perakende Fiyat Katmanı

**Sağlayıcı:** TÜBİTAK BİLGEM + TCMB

**Erişim yöntemi:** Web scraping. robots.txt tamamen açık: `User-agent: * / Allow: /` (yalnızca `/404` engellidir). Sitemap'ler mevcuttur: `sitemap-1.xml` ve `sitemap-2.xml` tüm ürün URL'lerini listeler; `categories.xml` 72 kategoriyi listeler.

**Konum bazlı fiyat verisi:** Platform konum bilgisi ile çalışmaktadır. Kullanıcı konumuna göre yakın mağazaların fiyatları listelenmektedir. Mağaza bazlı fiyatlama bilgisi mevcuttur — aynı ürünün farklı şubelerde farklı fiyatları olabilmektedir. Bu konum verisi scraping sırasında farklı il/ilçe koordinatları ile sorgu yapılarak elde edilebilir.

**Veri formatı:** HTML → yapılandırılmış JSON'a parse. URL pattern: `/detay/{product_code}/{product-slug}` (örn: `/detay/005A/duru-pilavlik-pirinc-2000-gr`).

**İçerik:** 50.000 ürün, 72 alt kategori, 7 market fiyatı (A101, BİM, ŞOK, Migros, CarrefourSA, Hakmar, Tarım Kredi), stok durumu ("Mevcut Değil" bilgisi), birim fiyat.

**Güncellenme:** Günlük.

**Tarihsel derinlik:** Platform Şubat 2025'te açıldı. Tarihsel veri sunmuyor — pipeline kendi günlük snapshot arşivini oluşturacak.

**Tahmini hacim:** 50K ürün × 7 market × konum varyasyonları × günlük snapshot = ~500 MB–1 GB/gün. Yıllık: ~180–360 GB.

**İl bazlı scraping stratejisi:** 81 il merkezi için koordinat listesi hazırlanır. Her il için ayrı request ile o bölgedeki mağaza fiyatları çekilir. Bu, aynı ürünün İstanbul Kadıköy'deki Migros'ta vs. Erzurum'daki Migros'ta farklı fiyatlanıp fiyatlanmadığını ortaya koyar.

### 5.2. İBB Hal Ürünleri ve Fiyatları API — Toptan Giriş Fiyatı Katmanı (İstanbul)

**Sağlayıcı:** İstanbul Büyükşehir Belediyesi Tarımsal Hizmetler Dairesi Başkanlığı

**URL:** Swagger API: `https://halfiyatlaripublicdata.ibb.gov.tr/swagger/ui/index`

**Erişim yöntemi:** REST API (Swagger dokümantasyonu ile). İBB Açık Veri Lisansı (CC BY 4.0 benzeri) ile ücretsiz.

**API endpoint'leri:** Bütün ürün kategorileri, bütün hal türleri, bütün birim türleri, bütün ürünler, güne göre ürün fiyatları, güne ve hal türüne göre ürün fiyatları, ve ürün ID'sine göre o ürünün tüm günlerdeki fiyat tarihçesi sorgulanabilmektedir.

**İçerik:** Meyve, sebze ve ithal meyve-sebze fiyatları. Her ürün için min/max/ortalama fiyat. Bayrampaşa (Avrupa yakası) ve Ataşehir (Anadolu yakası) hal verileri.

**Veri formatı:** JSON (REST API).

**Güncellenme:** Günlük.

**Tarihsel derinlik:** API üzerinden geçmişe dönük sorgu desteklenmektedir. Veri seti 2020'den beri erişilebilir durumdadır.

**Tahmini hacim:** ~5–10 GB (tüm tarihsel veriler).

### 5.3. İBB Hal Aylık Tonaj Verileri — Arz Miktarı Katmanı

**Sağlayıcı:** İBB Tarımsal Hizmetler Dairesi Başkanlığı

**URL:** `data.ibb.gov.tr` (tag: "hal")

**Erişim:** CSV/XLSX download + CKAN API.

**İçerik:** Bayrampaşa ve Ataşehir hallerine giriş yapan meyve ve sebzelerin aylık tonajları. Araç giriş sayıları.

**Veri formatı:** CSV/XLSX.

**Güncellenme:** Aylık.

**Tarihsel derinlik:** Yıllar bazında mevcut.

**Tahmini hacim:** ~500 MB.

### 5.4. İzmir BB Hal Fiyatları API — İkinci Şehir Karşılaştırması

**Sağlayıcı:** İzmir Büyükşehir Belediyesi

**URL:** API: `https://openapi.izmir.bel.tr/api/ibb/halfiyatlari/sebzemeyve/{yyyy-MM-dd}`. CSV bulk: `https://openfiles.izmir.bel.tr/100194/docs/izbb-sebzemeyve-hal-fiyatlari.csv`

**Erişim:** REST API (tarih parametreli) + CSV bulk download.

**İçerik:** Tarih, sebze/meyve türü, adı, ölçü birimi, asgari/azami/ortalama fiyatlar.

**Veri formatı:** JSON (API) + CSV (bulk).

**Güncellenme:** Günlük.

**Tarihsel derinlik:** 2024 yılı CSV mevcut; API ile geçmişe dönük sorgu.

**Tahmini hacim:** ~2–5 GB.

### 5.5. GDELT v2 — Gıda Haberleri ve Ton Analizi

**Sağlayıcı:** GDELT Project.

**Erişim:** BigQuery (1 TB/ay ücretsiz) + CSV download.

**Veri formatı:** TSV / BigQuery SQL.

**Güncellenme:** 15 dakikada bir (gerçek zamanlı).

**Tarihsel derinlik:** Şubat 2015'ten bugüne.

**Gıda-spesifik GKG temaları:** `FOOD_SECURITY`, `FUELPRICES`, `ECON_INFLATION`, `ECON_COSTOFLIFE`, `ECON_PRICECONTROLS`, `ENV_DROUGHT`, `ENV_NATURALGAS`.

**Ek filtreler:** `Actor1CountryCode='TUR'` veya `ActionGeo_CountryCode='TU'` (FIPS). V2Tone ile haber tonalitesi (-100 ile +100 arası).

**Tahmini hacim:** ~50–100 GB/yıl (Türkiye + gıda filtreli).

### 5.6. Türk Gıda/Ekonomi Haber RSS Feed'leri

**Erişim:** RSS/Atom XML polling (feedparser).

**Kullanılacak feed'ler:** AA Ekonomi (`aa.com.tr/tr/rss/default?cat=ekonomi`), BBC Türkçe (`feeds.bbci.co.uk/turkce/rss.xml`), DW Türkçe (`rss.dw.com/xml/rss-tur-all`), CNN Türk (`cnnturk.com/feed/rss/all/news`).

**Güncellenme:** Sürekli.

**Tahmini hacim:** ~2–5 GB/ay.

### 5.7. Open-Meteo Hava Durumu API — Tarımsal Şok Tespiti

**Erişim:** REST API, API key gereksiz, tamamen ücretsiz.

**İçerik:** Sıcaklık, don riski, yağış, rüzgar hızı, güneş radyasyonu. Türkiye'nin tarım bölgeleri (Antalya, Mersin, Adana — Akdeniz; Bursa, Balıkesir — Marmara; Konya, Ankara — İç Anadolu) için saatlik veriler.

**Tarihsel derinlik:** 1940'tan bugüne (ERA5 reanalysis).

**Tahmini hacim:** ~20–50 GB (81 il, saatlik, tüm tarihsel).

### 5.8. EPİAŞ + TCMB EVDS — Enerji ve Makro Göstergeler

**EPİAŞ:** Saatlik PTF (elektrik fiyatı), toplam tüketim, kaynak bazlı üretim. `eptr2` Python kütüphanesi ile. Tarihsel: 2016+.

**TCMB EVDS:** USD/TRY, EUR/TRY döviz kurları, tarımsal girdi fiyat endeksleri, enerji ithalat fiyatları, resmi TÜFE alt kalemleri (gıda, enerji vb.), beklenen enflasyon anketi. `evdspy` Python kütüphanesi ile. Tarihsel: 1950'ler+.

**Tahmini hacim:** EPİAŞ ~50–80 GB, TCMB ~5–10 GB.

---

## 6. Tahmini Toplam Veri Büyüklüğü

| Kaynak | Başlangıç Hacmi | Yıllık Artış | Format |
|--------|----------------|-------------|--------|
| marketfiyati.org.tr (il bazlı, günlük) | ~25 GB | ~360 GB/yıl | HTML→JSON |
| İBB Hal API (tarihsel + günlük) | ~10 GB | ~2 GB/yıl | JSON |
| İBB Hal Tonaj (aylık) | ~500 MB | ~100 MB/yıl | CSV |
| İzmir Hal API + CSV | ~5 GB | ~1 GB/yıl | JSON/CSV |
| GDELT (TR + gıda filtreli) | ~100 GB | ~50 GB/yıl | TSV |
| RSS Feed'ler | ~5 GB | ~30 GB/yıl | XML→JSON |
| Open-Meteo (81 il, saatlik) | ~30 GB | ~5 GB/yıl | JSON |
| EPİAŞ + TCMB | ~90 GB | ~16 GB/yıl | JSON/CSV |
| **TOPLAM** | **~265 GB** | **~464 GB/yıl** | **5 farklı format** |

İl bazlı scraping (81 il × 50K ürün) veri hacmini dramatik artırır. 1 TB'a ilk yılda ulaşılır.

---

## 7. Veri Nasıl Toplanacak — Ingestion Mimarisi

### 7.1. Stream Kaynakları (Gerçek/Yarı-Gerçek Zamanlı)

```
┌────────────────────────────────┐
│  marketfiyati.org.tr           │
│  (81 il × 50K ürün × 7 market)│──günlük scrape──▶┐
│  konum bazlı fiyatlar          │                   │
├────────────────────────────────┤                   │
│  İBB Hal API                   │──günlük poll─────▶│
│  (Bayrampaşa + Ataşehir)      │                   │     ┌─────────────┐
├────────────────────────────────┤                   ├────▶│   KAFKA     │
│  İzmir Hal API                 │──günlük poll─────▶│     │  CLUSTER    │
│  (İzmir Hal)                  │                   │     │ (10 topic)  │
├────────────────────────────────┤                   │     └──────┬──────┘
│  GDELT 2.0                    │──15 dk polling───▶│            │
│  (gıda temaları)              │                   │            ▼
├────────────────────────────────┤                   │     ┌──────────────┐
│  RSS Feed'ler                 │──5 dk polling────▶│     │    FLINK     │
│  (ekonomi/gıda haberleri)     │                   │     │   STREAM     │
├────────────────────────────────┤                   │     │  PROCESSING  │
│  Open-Meteo                   │──saatlik poll────▶│     └──────┬───────┘
│  (tarım bölgeleri hava)       │                   │            │
├────────────────────────────────┤                   │            ▼
│  EPİAŞ API                    │──saatlik poll────▶│     ┌──────────────┐
│  (elektrik fiyatı)            │                   │     │  DELTA LAKE  │
├────────────────────────────────┤                   │     │  MEDALLION   │
│  TCMB EVDS                    │──günlük poll─────▶┘     │  (Bronze →   │
└────────────────────────────────┘                        │   Silver →   │
                                                          │   Gold)      │
                                                          └──────┬───────┘
                                                                 │
                                                     ┌───────────┼───────────┐
                                                     ▼           ▼           ▼
                                                [Grafana]   [Superset]  [FastAPI]
```

### 7.2. Kafka Topic Yapısı

```
market.prices.daily.{il_kodu}     — İl bazlı perakende fiyatlar (81 topic veya partitioned)
market.prices.changes             — Fiyat değişiklik CDC event'leri
hal.istanbul.prices.daily         — İBB hal günlük fiyatlar
hal.istanbul.tonnage.monthly      — İBB hal aylık tonaj
hal.izmir.prices.daily            — İzmir hal günlük fiyatlar
hal.market.margin.daily           — Hesaplanmış hal→market marjları
gdelt.turkey.food                 — GDELT gıda temalı event/GKG
rss.turkey.economy                — RSS ekonomi/gıda haberleri
weather.turkey.agriculture        — Tarım bölgeleri hava durumu
energy.macro.daily                — EPİAŞ + TCMB birleşik göstergeler
```

### 7.3. İl Bazlı Scraping Stratejisi

**Adım 1:** 81 il merkezi koordinat listesi hazırla (örn: İstanbul Kadıköy: 40.9833, 29.0333; Ankara Kızılay: 39.9208, 32.8541; İzmir Konak: 38.4192, 27.1287; ...).

**Adım 2:** Her il için marketfiyati.org.tr'ye konum bilgisi ile request gönder.

**Adım 3:** O bölgedeki mağaza fiyatlarını parse et.

**Adım 4:** Aynı ürünün farklı illerdeki fiyat farklarını Delta Lake'e yaz.

**Adım 5:** İl × Market × Ürün × Tarih boyutlu OLAP küpü oluştur.

**Zamanlama:** 81 il × ~50K ürün × 7 market = ~28 milyon fiyat noktası/gün. Scrapy cluster ile paralel çalışma gerekir. Gece saatlerinde (02:00-06:00) zamanlanır.

---

## 8. Realtime Veri Pipeline Detayı

### Pipeline 1 — Hal→Market Marj Hesaplama

```
[İBB Hal API]──günlük──▶ Hal ürünleri (domates sofralık: min 8, max 12, ort 10 TL/kg)
                              │
                              │  Entity Resolution Engine
                              │  (hal "Domates Sofralık Sera" ≈ market "domates-sofralik-kg"?)
                              │
[marketfiyati.org.tr]──günlük──▶ Market ürünleri (domates sofralık: A101=22, BİM=24, Migros=28 TL/kg)
                              │
                              ▼
                    ┌─────────────────────────────┐
                    │     MARJ HESAPLAMA           │
                    │                             │
                    │  Marj(A101) = 22 - 10 = 12  │  (%120 markup)
                    │  Marj(BİM)  = 24 - 10 = 14  │  (%140 markup)
                    │  Marj(Migros)= 28 - 10 = 18  │  (%180 markup)
                    │                             │
                    │  Sektör ort. marj = %146.7   │
                    └─────────────────────────────┘
```

**Entity resolution zorluğu:** Hal'deki ürün adları (örn: "Domates Sofralık Sera", "Biber Sivri", "Elma Starking") ile marketfiyati.org.tr'deki slug'lar (örn: "domates-sofralik-kg", "sivri-biber-500-gr", "starking-elma-kg") arasında fuzzy eşleme gerekir. Yaklaşım: Türkçe text normalizasyonu → TF-IDF vektörizasyon → cosine similarity → eşik üstü eşleşmeleri insan doğrulaması → mapping tablosu.

### Pipeline 2 — İl Bazlı Fiyat Eşitsizlik Analizi

```
[81 il scraping sonuçları]
         │
         ▼
┌─────────────────────────────────────┐
│  ÜRÜN × İL × MARKET × TARİH KÜPÜ  │
│                                     │
│  Domates, İstanbul, Migros: 28 TL   │
│  Domates, Ankara, Migros: 26 TL     │
│  Domates, Antalya, Migros: 20 TL    │  ← Üretim bölgesinde ucuz
│  Domates, Erzurum, Migros: 32 TL    │  ← Uzak bölgede pahalı
│                                     │
│  Fiyat varyans katsayısı (CV):     │
│  Domates: CV = 0.18 (yüksek)       │
│  Süt: CV = 0.03 (düşük)            │  ← Homojen fiyatlama
│                                     │
│  İl bazlı "pahalılık endeksi":     │
│  İstanbul = 1.12 (ortalama +%12)    │
│  Antalya = 0.88 (ortalama -%12)     │
│  Hakkari = 1.25 (ortalama +%25)     │
└─────────────────────────────────────┘
```

### Pipeline 3 — Hava Şoku → Fiyat Propagasyon Analizi

```
[Open-Meteo] Don olayı tespiti: Antalya, 3 Ocak, -2°C
         │
         │  Gün 0: Don olayı
         │  Gün 1-3: Antalya hal fiyatlarında artış başlangıcı
         │  Gün 3-5: İstanbul hal fiyatlarında artış
         │  Gün 5-10: Market fiyatlarında artış
         │  Gün 7-14: Diğer illerde yayılım
         │
         ▼
┌─────────────────────────────────────┐
│  ŞOK PROPAGASYON ZAMANLAMA MATRİSİ │
│                                     │
│  Don→Antalya Hal: 1-3 gün lag       │
│  Don→İstanbul Hal: 3-5 gün lag      │
│  İstanbul Hal→İstanbul Market:      │
│    A101: 2 gün lag                  │
│    Migros: 3 gün lag                │
│    BİM: 1 gün lag                   │
│                                     │
│  Toplam don→tüketici: 5-10 gün     │
└─────────────────────────────────────┘
```

### Pipeline 4 — Asimetrik Fiyat Geçişkenliği (Rockets & Feathers)

```
[Hal fiyatı ↓ %20]                    [Hal fiyatı ↑ %20]
      │                                     │
      ▼                                     ▼
  Market tepki hızı:                   Market tepki hızı:
  - A101: 5 gün lag, -%12 geçiş       - A101: 2 gün lag, +%18 geçiş
  - Migros: 8 gün lag, -%8 geçiş      - Migros: 1 gün lag, +%22 geçiş
  - BİM: 4 gün lag, -%15 geçiş        - BİM: 2 gün lag, +%16 geçiş
      │                                     │
      ▼                                     ▼
  FEATHER (tüy — yavaş iniş)          ROCKET (roket — hızlı çıkış)
  "Düşüşler gecikmeli ve eksik"       "Artışlar hızlı ve fazla"
      │                                     │
      └──────────┬───────────────────────────┘
                 ▼
         ASİMETRİ KATSAYISI
         = (artış hızı / düşüş hızı) - 1
         > 0 ise tüketici aleyhine asimetri
```

### Pipeline 5 — GDELT Haber → Fiyat Korelasyonu

```
[GDELT GKG]                          [RSS Feed'ler]
  │ V2Themes LIKE '%FOOD_SECURITY%'    │ "domates fiyatları" haberleri
  │ V2Tone = -8.5 (olumsuz)           │ tam metin Türkçe
  │                                    │
  └────────────┬───────────────────────┘
               ▼
        [Temporal Alignment]
               │
               ▼
   [marketfiyati.org.tr domates fiyat değişimleri]
               │
               ▼
   Granger Causality Test (statsmodels):
   H0: "Haber tonu domates fiyatını Granger-önceler mi?"
   p < 0.05 ise haber→fiyat nedenselliği var

   Cross-correlation (lag 0–14 gün):
   "GDELT negatif ton spike'ından 3 gün sonra
    domates market fiyatında %5 artış gözleniyor"
```

---

## 9. Data Engineering Zorluk Noktaları

### 9.1. Entity Resolution: Hal → Market Ürün Eşleme

Bu projenin en kritik data engineering zorluğudur. İBB Hal API'sindeki ürün isimleri (örn: "Domates Sofralık Sera", "Biber Sivri Yeşil", "Elma Starking Kırmızı") ile marketfiyati.org.tr'deki slug'lar (örn: "domates-sofralik-kg", "sivri-biber-500-gr", "starking-elma-kg") tamamen farklı yapıdadır. Hal verileri kg bazlı toptan ürünler iken market verileri markalı, gramajlı perakende ürünlerdir. Bir hal ürünü (örn: "Domates Sofralık") markette onlarca farklı SKU'ya karşılık gelir (domates sofralık kg, domates kokteyl 500gr, domates salkım kg, vb.). Çözüm yaklaşımı şöyledir: Türkçe metin normalizasyonu (küçük harf, özel karakter temizleme, stop word kaldırma), TF-IDF vektörizasyon + cosine similarity ile aday eşleşmeler, COICOP kategorisi çapraz referans (hal kategorisi ↔ market kategorisi), insan doğrulamalı mapping tablosu oluşturma (bir kez), ve yeni ürünler için otomatik sınıflandırıcı (scikit-learn, CPU-only).

### 9.2. Birim Harmonizasyonu

Hal verileri kg ve kasa bazında toptan fiyatlar sunarken, market verileri gram, adet, paket, litre gibi farklı birimler kullanır. Birim fiyat dönüşüm motoru gerekir. Örnekler: "domates sofralık kg" (hal) vs. "domates sofralık 500 gr" (market) → market fiyatını 2 ile çarp. "Elma kg" (hal) vs. "elma 3 adet" (market) → ortalama elma ağırlığı ~200g → 3 adet ≈ 600g. Gramaj bilgisi marketfiyati.org.tr slug'larından regex ile çıkarılır: `(\d+)\s*(gr|kg|ml|lt|adet)`.

### 9.3. İl Bazlı Geospatial Data Management

81 il × 50K ürün × 7 market = günde 28+ milyon fiyat noktası. Bu verinin verimli depolanması H3 hexagonal grid (Uber'in spatial indexing sistemi) veya PostGIS ile il/ilçe bazlı partitioning gerektirir. Spatial join'ler (hangi market hangi ile ait?) ve proximity sorgular (en yakın hal hangisi?) PostGIS ile yapılır.

### 9.4. Multi-Resolution Temporal Alignment

Sekiz farklı veri kaynağı sekiz farklı zamanlama ile güncellenir: marketfiyati.org.tr günlük, İBB Hal API günlük, İBB tonaj aylık, İzmir Hal günlük, GDELT 15 dakikalık, RSS sürekli, Open-Meteo saatlik, EPİAŞ saatlik, TCMB günlük. Tümünü tutarlı günlük pencereye hizalamak event-time watermark yönetimi ve MIDAS (Mixed Data Sampling) regresyon gerektirir.

### 9.5. SCD Type 2 Fiyat Geçmişi

marketfiyati.org.tr anlık fiyat gösterir, tarihsel veri sunmaz. Pipeline günlük snapshot alarak kendi tarihsel veritabanını oluşturur. Her ürün × market × il kombinasyonu için fiyat değişikliklerini takip eden Slowly Changing Dimension Type 2 tablosu tasarlanır: `product_id`, `market_id`, `city_id`, `price`, `valid_from`, `valid_to`, `is_current`. İl bazlı scraping ile bu tablo çok hızlı büyür.

### 9.6. Multi-City Hal Schema Harmonizasyonu

İBB Hal API (Swagger/JSON) ve İzmir Hal API (REST/JSON + CSV) farklı şema yapıları kullanır. Ürün isimleri, kategori kodları ve birim tanımları farklıdır. Birleşik canonical hal şeması tasarlanmalıdır. Gelecekte Ankara, Bursa, Antalya hal verileri de eklenebilir — şema genişletilebilir olmalıdır.

### 9.7. Scraping Güvenilirliği

marketfiyati.org.tr'nin HTML yapısı değişebilir, yeni marketler eklenebilir (şu an 7), ürün kodları değişebilir. Schema drift detection (günlük parse edilen alan sayısı kontrolü), scraping health monitoring (başarılı/başarısız request oranı), ve fallback mekanizmaları (son bilinen fiyatı kullan + alert gönder) gerekir.

---

## 10. Machine Learning Kullanımı (Opsiyonel, Destekleyici)

Tüm modeller CPU-only, GPU gereksiz.

**Entity Resolution (TF-IDF + Cosine Similarity + Active Learning):** Hal ürünlerinin market ürünlerine eşlenmesi. scikit-learn TF-IDF vektörizasyon ile. İlk eşleşmeler insan doğrulamasıyla, sonrası otomatik sınıflandırıcıyla.

**Anomali Tespiti (Isolation Forest):** Fiyat anomalileri — aynı ürünün 7 marketteki fiyatı arasında anormal sapmalar. Veri kalite hatası vs. gerçek fiyat anomalisi ayrımı.

**Asimetrik Geçişkenlik Modeli (Error Correction Model):** Engle-Granger iki aşamalı kointegrasyon testi ile hal ve market fiyatları arasında uzun dönem ilişki, ardından asimetrik hata düzeltme modeli ile yukarı/aşağı geçişkenlik hızı ölçümü.

**Granger Causality ve Cross-Correlation:** GDELT ton değişimleri → market fiyat değişimleri nedensellik testi (statsmodels). Hava durumu şokları → hal fiyatı → market fiyatı lag tespiti (0–30 gün).

**Ürün Slug Parsing (Regex + spaCy):** marketfiyati.org.tr slug'larından marka, gramaj, birim ve ürün tipi çıkarma. Türkçe spaCy modeli (tr_core_news_sm, CPU-only).

---

## 11. Dashboard / Görselleştirme Fikri

### Ana Dashboard — "GıdaRadar Turkey"

**Panel 1 — Türkiye Fiyat Haritası (Choropleth):** 81 il bazında seçili ürünün (örn: 1 kg kıyma) ortalama perakende fiyatı. Renk skalası: yeşil (ucuz) → kırmızı (pahalı). İl tıklandığında market bazlı breakdown açılır. Heatmap overlay: hal fiyatı vs. market fiyatı marjı.

**Panel 2 — Hal→Market Marj Tracker:** Seçili ürün için zaman serisi: hal fiyatı (çizgi) vs. 7 market fiyatı (7 çizgi). Aradaki alan (marj) dolgu ile gösterilir. Marj trendinin artan/azalan olduğu görsel olarak anlaşılır.

**Panel 3 — Şok Propagasyon Zaman Çizelgesi:** Hava durumu olayı (don, sel, kuraklık) → hal fiyat tepkisi → market fiyat tepkisi timeline. Sankey diagram: üretim bölgesi → hal → market → tüketici fiyat akışı.

**Panel 4 — Rockets & Feathers Analizi:** Seçili ürün ve market için hal fiyat artışı vs. düşüşü sonrasında market tepki hızı karşılaştırması. Asimetri katsayısı gauge'u.

**Panel 5 — Market Karşılaştırma Scorecard:** 7 market × 12 COICOP kategorisi matris. Her hücrede: ortalama marj, fiyat değişim frekansı, hal fiyat düşüşünü geçirme hızı. Renk kodlaması: tüketici dostu (yeşil) → tüketici aleyhine (kırmızı).

**Panel 6 — Haber Pulse:** GDELT + RSS'den son gıda haberleri. Ton endeksi trendi. Haber→fiyat lag scatter plot.

---

## 12. Önerilen Teknik Stack

**Scraping:** Scrapy cluster (81 il paralel), BeautifulSoup (HTML parse), Playwright (JS-rendered sayfalar için yedek).

**Stream Ingestion:** Apache Kafka (3+ broker, 10+ topic).

**Stream Processing:** Apache Flink (entity resolution, marj hesaplama, asimetri tespiti, şok propagasyon pencereler).

**Batch Processing:** Apache Spark (tarihsel backfill, GDELT BigQuery export, Granger causality, cointegration testleri). dbt (Silver→Gold SQL transformasyonları, OLAP küp materialization).

**Orchestration:** Apache Airflow (günlük scrape DAG'ları, haftalık model re-training, aylık tonaj import, veri kalite kontrolleri).

**Data Quality:** Great Expectations (fiyat aralık kontrolleri, tamlık kontrolleri, il başına ürün sayısı tutarlılık kontrolü, yeni ürün/silinen ürün tespiti).

**Storage — Medallion Architecture:** Bronze katmanı Delta Lake on MinIO/S3 — ham HTML (marketfiyati.org.tr), raw JSON (hal API'leri, EPİAŞ, EVDS), raw TSV (GDELT), raw XML (RSS). Silver katmanı Delta Lake — temizlenmiş, şema uygulanmış, entity resolution yapılmış veriler: `silver.market_prices` (SCD Type 2 — ürün × market × il × tarih), `silver.hal_prices` (İstanbul + İzmir birleşik), `silver.hal_market_mapping` (entity resolution tablosu), `silver.gdelt_food_events`, `silver.weather_agriculture`. Gold katmanı Delta Lake — analitik-ready: `gold.daily_margin_by_product_market_city` (ürün × market × il × tarih marj tablosu), `gold.price_inequality_by_city` (il bazlı fiyat eşitsizlik endeksi), `gold.shock_propagation_matrix` (hava→hal→market lag tablosu), `gold.asymmetric_passthrough_scores` (rockets & feathers katsayıları), `gold.news_price_correlation`.

**Geospatial:** PostgreSQL + PostGIS (il/ilçe sınırları, market konumları, hal konumları), H3 hexagonal grid (spatial aggregation).

**Serving:** PostgreSQL (Gold katmanı materialize view'lar), Redis (son marj değerleri, anomali flag'leri, il bazlı endeksler), FastAPI (REST API — marj sorgulama, il karşılaştırma endpoint'leri).

**Dashboard:** Apache Superset (birincil — Türkiye haritası, OLAP drill-down, SQL Lab), Grafana (gerçek zamanlı alerting, time-series paneller), Kepler.gl (geospatial görselleştirme — il bazlı fiyat haritası).

**Python Kütüphaneleri:** `scrapy` + `beautifulsoup4` (web scraping), `eptr2` (EPİAŞ API), `evdspy` (TCMB EVDS API), `feedparser` (RSS parsing), `google-cloud-bigquery` (GDELT BigQuery), `pytrends` (Google Trends), `scikit-learn` (entity resolution, anomali tespiti), `statsmodels` (Granger causality, cointegration, ECM), `spacy` + `tr_core_news_sm` (Türkçe NLP, CPU-only), `great_expectations` (veri kalite), `h3-py` (hexagonal spatial indexing), `geopandas` (geospatial data processing).

---

## 13. Projeyi Benzersiz Kılan Özellikler

Birincisi, hal→market marj analizi hiç yapılmamıştır. İBB hal fiyatları ile marketfiyati.org.tr perakende fiyatlarını birleştiren açık kaynaklı bir proje dünyada mevcut değildir. İkincisi, il bazlı fiyat eşitsizlik haritası Türkiye'de ilk olacaktır. 81 il × 7 market × 50K ürün boyutlu OLAP küpü Türk perakende sektörünün en kapsamlı veri tabanını oluşturur. Üçüncüsü, rockets & feathers analizi Türk perakende sektöründe hiç test edilmemiştir. Dördüncüsü, hava durumu → hal → market şok propagasyon zincirinin nicel ölçümü tarım ekonomisi literatürüne özgün katkı sağlar. Beşincisi, 8 farklı veri kaynağı ve 5 farklı format (HTML, JSON, CSV, TSV, XML) ile gerçek dünya data engineering karmaşıklığı master tez düzeyinde akademik değer taşır. Altıncısı, doğrudan karar destek çıktıları (Rekabet Kurumu, Ticaret Bakanlığı, TCMB) projeye politika değeri katmaktadır.

---

## 14. Proje Fazları

| Faz | Süre | Çıktı |
|-----|------|-------|
| **Faz 1: Veri Keşfi ve Erişim Doğrulama** | 2 hafta | marketfiyati.org.tr scraping POC (3 il test), İBB Hal API Swagger test, İzmir Hal API test, GDELT BigQuery test sorguları, konum bazlı veri yapısı analizi |
| **Faz 2: Entity Resolution Pipeline** | 3 hafta | Hal↔market ürün eşleme tablosu, birim harmonizasyon motoru, COICOP kategori eşleme, TF-IDF sınıflandırıcı eğitimi |
| **Faz 3: Scraping Infrastructure** | 3 hafta | Scrapy cluster kurulumu, 81 il koordinat listesi, günlük tam scrape pipeline'ı, SCD Type 2 fiyat tablosu, Great Expectations kontrolleri, Airflow DAG'ları |
| **Faz 4: Multi-Source Integration** | 3 hafta | Kafka cluster (10 topic), GDELT/RSS/EVDS/EPİAŞ/Open-Meteo ingestion, Delta Lake medallion mimarisi, multi-resolution temporal alignment |
| **Faz 5: Analitik Engine** | 3 hafta | Marj hesaplama pipeline, il bazlı fiyat eşitsizlik endeksi, asimetrik geçişkenlik modeli (ECM), şok propagasyon lag analizi, Granger causality testleri |
| **Faz 6: Dashboard ve API** | 2 hafta | Superset dashboard (Türkiye haritası, marj tracker, scorecard), Grafana alerting, FastAPI REST endpoint'leri, Kepler.gl geospatial harita |
| **Faz 7: Backtesting ve Doğrulama** | 2 hafta | Şubat 2025–bugün verisiyle model doğrulama, TÜİK TÜFE gıda alt kalemi ile karşılaştırma, akademik rapor yazımı |
| **TOPLAM** | **~18 hafta** | Uçtan uca çalışan platform |

---

*Bu doküman Mart 2026 itibarıyla doğrulanmış ve erişilebilir veri kaynaklarına dayanmaktadır.*
*marketfiyati.org.tr robots.txt: Allow: / (26 Mart 2026 doğrulanmıştır).*
*İBB Hal API: Swagger UI aktiftir. İBB Açık Veri Lisansı (CC BY 4.0 benzeri) ile ücretsiz kullanılabilir.*
*İzmir Hal API: REST endpoint aktiftir. 2024 CSV bulk download mevcuttur.*
