
---

# Proje Başlığı: Türkiye Gıda Tedarik Zinciri Şeffaflık ve İl Bazlı Marj Analizi Motoru

*(Türkiye Food Supply Chain Transparency and Spatial Margin Analysis Engine)*

> **Disclaimer:** Bu projede içerik üretimi ve mimari tasarım aşamalarında yapay zeka araçlarından yararlanılmıştır.

proje detayları için @project.md ye bak

## 1\. Business Problemi

Türkiye'de tarım ürünlerinin tarladan çıkış fiyatı ile büyükşehirlerdeki market raflarına ulaşan fiyatı arasındaki uçurum, sürekli tartışılan ancak **sistematik ve veri odaklı ölçülemeyen** bir "kara kutudur".

Bu proje şu spesifik iş ve analiz problemlerini çözer:

* **İl Bazlı Tedarik Zinciri Marjı:** İstanbul Hal'ine 10 TL'ye giren domates, İstanbul Kadıköy'deki X marketinde 35 TL iken, İzmir Hal'ine 8 TL'ye giren domates İzmir Karşıyaka'daki aynı X marketinde neden 25 TL? Aradaki marj şehre, markete ve ürün grubuna göre nasıl değişiyor? Marj kategorilere (sebze, meyve, tahıl vb.) göre nasıl farklılaşıyor?
* **Şok Yayılım Hızı (Shock Propagation):** Antalya'da don olayı (Open-Meteo + Sentinel-2 NDVI) yaşandığında, bu arz şoku İBB Hal Toptan fiyatlarına kaç günde, oradan da zincir marketlerin perakende fiyatlarına kaç günde yansıyor?
* **Asimetrik Fiyat Geçişkenliği (Rockets and Feathers):** Hal toptan fiyatları düştüğünde, zincir marketler bu indirimi tüketiciye ne kadar gecikmeli yansıtıyor? Fiyat arttığında ne kadar hızlı yansıtıyor?
* **Lojistik Maliyet Etkisi:** Enerji/Akaryakıt/Elektrik (TCMB/EPİAŞ) fiyatlarındaki artış, hal-market marjını ne ölçüde ve hangi gecikmeyle açıklıyor?
* **Pandemi Etkisi:** Pandemi öncesi ve sonrası dönemlerde domates başta olmak üzere temel ürünlerdeki hal-market fiyat marjı farkı açılıyor mu? Yapısal kırılma ne zaman gerçekleşti?
* **Zaman Serisi Tahmini:** Prophet (Meta) ile domates ve diğer temel ürünlerin gelecek fiyat trendi tahmini; son 10 yıllık domates fiyatı time-series analizi.

## 2\. Türkiye İle Bağlantısı

Gıda fiyatlarındaki oynaklık ve "aracı kurumların" kâr marjları, Ticaret Bakanlığı, Rekabet Kurumu, Merkez Bankası ve tüketiciler için Türkiye'nin en büyük yapısal problemlerinden biridir. Bu proje, devlet kurumları için bir **Karar Destek Sistemi (DSS)**, Rekabet Kurumu için bir **Erken Uyarı Radarı** niteliği taşır. Haksız fiyat artışlarını, lokasyon bazlı spekülasyonları ve medya haberlerinin (GDELT) fiyatlar üzerindeki psikolojik etkisini gerçek veriyle kanıtlar.

### Benzer Ürünler / Literatür Araştırması

Dünyada benzer tedarik zinciri şeffaflık projeleri incelenmiştir:
* Avrupa'da "Farm-to-Fork" fiyat izleme sistemleri (AB Komisyonu veri portalları)
* FAO'nun tarımsal fiyat geçişkenliği araştırmaları
* İBB ve diğer belediyelerin hal fiyat takip sistemleri
* Akademik literatürde "price transmission asymmetry" ve "rockets and feathers" çalışmaları

Literatür taraması yapılacak konular: Türkiye gıda fiyat geçişkenliği, hal-perakende marj analizi, arz şoku yayılımı.

## 3\. Kullanılabilecek Veri Kaynakları

Bu proje, birbirinden tamamen bağımsız formatlarda, farklı granülaritelerde ve farklı şemalarda akan verilerin entegrasyonunu gerektirir.

| Veri Kaynağı | Sağlayıcı | Erişim Yöntemi | Veri Formatı | Boyut/Hacim | Güncellenme Sıklığı |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Market Perakende Fiyatları** | marketfiyati.org.tr | API / Webhook (Arşiv) | JSON (Nested) | \~15-20 GB/ay (50K ürün x 7 market x 81 İlçe/İl) | Günlük / Intraday |
| **İBB Hal Fiyatları & Taksonomi** | İBB Açık Veri Portalı | Swagger API | REST JSON | \~2-3 GB/yıl | Günlük |
| **İzmir Hal Fiyatları** | İzmir BB Açık Veri | API & Bulk CSV | CSV / JSON | \~1 GB/yıl | Günlük |
| **İBB Hal Tonaj Verileri** | İBB Açık Veri Portalı | Bulk Download | CSV | \~500 MB (Tarihsel) | Aylık |
| **Hava Durumu (Tarım Bölgeleri)** | Open-Meteo | REST API (Historical + Forecast) | JSON | \~5 GB/yıl (Saatlik/Noktasal) | Saatlik (Stream) |
| **Uydu / Bitki Sağlığı (NDVI)** | Sentinel-2 L2A | ESA Copernicus API | GeoTIFF | \~10 GB/yıl | 5 Günde Bir |
| **Gıda ve Tarım Haberleri** | GDELT Project | S3 Bucket / API | CSV (Zipped) | \~10-15 GB/yıl (Sadece TR) | 15 Dakikada Bir (Stream) |
| **Google News Haberleri** | Google News | RSS / API | JSON/XML | \~1 GB/yıl | Saatlik |
| **Elektrik (Soğuk Zincir)** | EPİAŞ Şeffaflık | Şeffaflık API | JSON | \~1 GB/yıl | Saatlik (Stream) |
| **Kur & Tarım Girdi Endeksi** | TCMB EVDS | EVDS API | XML / JSON | \< 100 MB | Günlük/Aylık |
| **Tarım ÜFE, USD/TRY** | TCMB / TÜİK | EVDS API | JSON | \< 100 MB | Aylık |
| **Ulaşım Maliyeti** | Çeşitli | API / CSV | JSON | \~500 MB/yıl | Haftalık |

## 4\. Metodoloji

### Araştırma Sorusu ve Hipotezler

**Ana Hipotez:** Türkiye'de hal-perakende fiyat marjı asimetriktir; fiyat artışları hızla yansırken düşüşler gecikmeli ve kısmi yansımaktadır.

**Alt Hipotezler:**
1. Don olayı sonrası hal fiyatları 1-3 günde tepki verirken perakende fiyatlar 3-7 günde tepki verir.
2. Pandemi sonrası dönemde (2021+) hal-perakende marjı yapısal olarak genişlemiştir.
3. Ankara-Konya gibi ana tarım güzergahlarındaki ulaşım maliyeti artışı marjı %X oranında açıklar.

### Analiz Yöntemi

1. **Betimsel Analiz:** İl ve ürün bazında marj dağılımı, zaman serisi grafikleri
2. **Ekonometrik Analiz:** Asimetrik Hata Düzeltme Modeli (AECM) — Rockets & Feathers testi
3. **Şok Analizi:** Event Study — don/sel olayı sonrası T+1, T+3, T+7 günlerde fiyat tepkisi
4. **Zaman Serisi Tahmini:** Meta Prophet ile domates fiyatı 30/90 günlük tahmin
5. **ML Modelleri:** XGBoost (marj tahmin regresyonu) + LSTM (fiyat serisi tahmini)

## 5\. Veri Nasıl Toplanacak (Ingestion Mimarisi & Data Engineering Zorlukları)

Bu projenin asıl mühendislik değeri **veri toplama ve uyumlaştırma (harmonization)** aşamasındadır.

### Data Engineering Zorlukları

1. **Entity Resolution (Semantik Eşleştirme):** İBB Hal API'sindeki ürün tanımı `"Domates Sofralık Sera"` iken, market API'sindeki ürün slug'ı `"salkim-domates-1-kg"` şeklindedir. TF-IDF yerine **Doc2Vec / Word2Vec** veya **Qwen dil modeli** kullanılarak anlamsal eşleştirme yapılacaktır.
2. **Birim Standardizasyonu:** Hal'de ürünler "Kasa", "Çuval" veya "Bağ" olarak fiyatlanabilir. Markette ise "Gram", "Adet" veya "Paket"tir. Ortak bir birime (1 KG) çevrim fonksiyonları (UDFs) geliştirilmelidir.
3. **Temporal & Spatial Alignment:** GDELT 15 dakikalık, EPİAŞ saatlik, Hal günlük, Tonaj aylıktır. Veriler S3/Parquet üzerinde "Time-series As-of Join" mantığı ile birleştirilmeli; il bazlı market verileri, o ile en yakın Hal verisiyle (Spatial join) eşleştirilmelidir.
4. **NDVI Entegrasyonu:** Sentinel-2 NDVI verisi ile tarım bölgelerindeki bitki sağlığı takip edilerek don/hasar olayları otomatik tespit edilecektir.

### Ingestion Pipeline Mimarisi

* **Real-time / Micro-batch (Apache NiFi → Kafka):** Open-Meteo (saatlik), EPİAŞ, GDELT haberleri ve `marketfiyati.org.tr`'den gelen gün içi fiyat güncellemeleri **Apache NiFi** üzerinden sürekli işlenerek Kafka Topic'lerine (`raw_weather`, `raw_gdelt`, `raw_market_prices`) basılır. NiFi batch'ler halinde sürekli process eden bir pipeline sağlar.
* **Batch (Apache NiFi zamanlama ile):** İBB ve İzmir Hal API'leri her gece saat 02:00'de NiFi tarafından tetiklenerek çekilir. TCMB EVDS verileri ve aylık Hal Tonaj CSV'leri periyodik olarak S3'e (Bronze Layer / Parquet) yazılır.

> **Not:** Apache Airflow self-hosted olarak kurulabilir ancak bu projede birincil orkestrasyon aracı olarak **Apache NiFi** kullanılmaktadır.

## 6\. Tahmini Veri Büyüklüğü ve Sıkıştırma

* **Ham Veri (JSON):** Başlangıç veritabanı **50-70 GB** bandında.
* **Parquet'e Geçişte Küçülme:** JSON → Parquet dönüşümü ile veri boyutu **~1/5 - 1/10** oranında küçülür. Örneğin: 200 GB JSON → ~20-40 GB Parquet (sütunsal sıkıştırma + şema optimizasyonu ile).
* **Ölçeklendirme:** 81 ile yayıldığında **~200 GB - 500 GB** (Parquet öncesi). EMR ile bu veri boyutunu işlemek hedeflenmektedir: "EMR'ı açıyorum, 500 GB veriyi X dakikada işleyip kapatıyorum" hedefi.

## 7\. Realtime Veri Pipeline (Medallion Architecture)

* **Bronze Layer (Raw — Parquet Format):** Kafka'dan okunan JSON'lar ve API'lerden gelen ham veriler **Parquet formatında** hiçbir yapısal değişikliğe uğramadan AWS S3 `bronze/` prefix'i altında saklanır. Parquet ile ~1/5 boyut küçülmesi sağlanır.
* **Silver Layer (Cleansed & Conformed):** Apache Flink / Spark Structured Streaming devreye girer.
  * Fiyatlardaki null değerler temizlenir.
  * Entity Resolution uygulanır (Doc2Vec / Qwen ile Hal ID ↔ Market Slug eşleştirmesi).
  * Birimler ortak formata (KG) çevrilir.
  * Stream üzerinden gelen saatlik don/aşırı yağış uyarıları ve NDVI anomalileri flag'lenir.
* **Gold Layer (Aggregated for Business):**
  * `daily_margin_by_city_and_market`: İl, Market ve Ürün bazında Hal ve Perakende arasındaki oransal uçurum; kategori bazlı breakdown (sebze / meyve / tahıl).
  * `shock_propagation_index`: Hava durumu şoku sonrası Hal'deki fiyat artışının markete yansıma gecikme süresi (gün).
  * `pandemic_gap_analysis`: Pandemi öncesi/sonrası marj karşılaştırması.

## 8\. Machine Learning

1. **Entity Resolution — Doc2Vec / Qwen:** TF-IDF yerine Doc2Vec veya Qwen dil modeli dump edilerek ürün isimlerinin anlamsal eşleştirmesi yapılacaktır. Qwen modeli lokal olarak çalıştırılabilir (offline embedding).
2. **Anomaly Detection (Isolation Forest):** Stream üzerinde hal fiyatı sabitken market fiyatında %50+ sıçrama tespiti.
3. **XGBoost — Marj Tahmin Regresyonu:** Hava, elektrik, kur, NDVI ve tonaj verilerini girdi olarak kullanarak bir sonraki haftanın hal-perakende marjını tahmin eder.
4. **LSTM — Fiyat Serisi Tahmini:** Domates ve diğer temel ürünler için 30/90 günlük fiyat tahmini.
5. **Prophet (Meta) — Trend & Seasonality:** Domates fiyatının son 10 yıllık zaman serisi analizi; pandemi kırılma noktası tespiti; gelecek 3 aylık tahmin.

## 9\. Dashboard / Görselleştirme

**Elasticsearch + Kibana (ELK Stack)** üzerinde 3 ana sekme:

1. **Türkiye Marj Haritası (Geo-Dashboard):** Türkiye haritası üzerinde, seçilen ürünün il bazında Hal'den Markete geçişteki kâr/maliyet marjı ısı haritası. Kategori filtresi (domates, biber, elma vb.).
2. **Geçişkenlik Radarı (Rockets & Feathers):** Hal Toptan fiyatı (mavi) ile Market Perakende fiyatının (kırmızı) zaman serisi; pandemi öncesi/sonrası karşılaştırma; Prophet tahmin bandı.
3. **Şok ve Haber Etkisi (Event Overlay):** GDELT/Google News haber olayları ve Open-Meteo + Sentinel-2 NDVI don uyarıları fiyat grafiği üzerine annotation olarak eklenir.

## 10\. Teknik Stack (AWS Odaklı)

Bu stack, endüstri standartlarında modern bir Data Engineering projesi olduğunu kanıtlar:

| Katman | Araç | Açıklama |
| :---- | :---- | :---- |
| **Ingestion / Orkestrasyon** | Apache NiFi | Batch + stream pipeline, sürekli veri akışı |
| **Message Broker** | Apache Kafka | Gerçek zamanlı topic bazlı mesaj kuyruğu |
| **Stream Processing** | Apache Flink | Entity resolution, birim dönüşümü, anomali tespiti |
| **Storage** | AWS S3 (Parquet) | Bronze/Silver/Gold katmanlı Medallion mimarisi |
| **Büyük Veri İşleme** | AWS EMR | 200-500 GB veriyi on-demand Spark cluster ile işleme |
| **Arama / Sorgulama** | Elasticsearch (ELK) | Delta Lake alternatifi, hızlı full-text + aggregation sorguları |
| **Visualization** | Kibana / Apache Superset | İl bazlı haritalar, zaman serisi, marj dashboard |
| **ML / Forecasting** | Prophet, XGBoost, LSTM, Qwen | Fiyat tahmini, entity resolution, anomaly detection |
| **SDK / Bağlantı** | boto3 | Python'dan AWS S3/EMR erişimi |
| **Deployment** | Docker / Docker-Compose + EC2 | Lokal geliştirme → EC2'ye taşıma |

### AWS Öncelik Sırası

1. **EC2** (micro/small/medium — büyük makine açmadan) — uygulama sunucusu
2. **S3** — ham ve işlenmiş veri depolama (boto3 ile erişim)
3. **EMR** — büyük veri işleme (ihtiyaç halinde açılır, işlem biter kapatılır)

## 11\. Referanslar

*(Sonraki sunuma eklenecek — akademik makaleler, FAO raporları, AB fiyat izleme sistemleri, benzer projelerin GitHub repoları)*

---

*Bu doküman ekip tarafından hazırlanmış olup içerik üretiminde yapay zeka araçlarından yararlanılmıştır.*
*Ekip: Azmi Yağlı, Abdullah Zengin, Hidayet Ersin Dursun*
