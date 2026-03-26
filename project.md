
---

# Proje Başlığı: Türkiye Gıda Tedarik Zinciri Şeffaflık ve İl Bazlı Marj Analizi Motoru

*(Turkey Food Supply Chain Transparency and Spatial Margin Analysis Engine)*

## 1\. Business Problemi

Türkiye'de tarım ürünlerinin tarladan çıkış fiyatı ile büyükşehirlerdeki market raflarına ulaşan fiyatı arasındaki uçurum, sürekli tartışılan ancak **sistematik ve veri odaklı ölçülemeyen** bir "kara kutudur".

Bu proje şu spesifik iş ve analiz problemlerini çözer:

* **İl Bazlı Tedarik Zinciri Marjı:** İstanbul Hal'ine 10 TL'ye giren domates, İstanbul Kadıköy'deki X marketinde 35 TL iken, İzmir Hal'ine 8 TL'ye giren domates İzmir Karşıyaka'daki aynı X marketinde neden 25 TL? Aradaki marj şehre, markete ve ürün grubuna göre nasıl değişiyor?  
* **Şok Yayılım Hızı (Shock Propagation):** Antalya'da don olayı (Open-Meteo) yaşandığında, bu arz şoku İBB Hal Toptan fiyatlarına kaç günde, oradan da zincir marketlerin perakende fiyatlarına kaç günde yansıyor?  
* **Asimetrik Fiyat Geçişkenliği (Rockets and Feathers):** Hal toptan fiyatları düştüğünde, zincir marketler bu indirimi tüketiciye ne kadar gecikmeli yansıtıyor? Fiyat arttığında ne kadar hızlı yansıtıyor?  
* **Lojistik Maliyet Etkisi:** Enerji/Akaryakıt/Elektrik (TCMB/EPİAŞ) fiyatlarındaki artış, hal-market marjını ne ölçüde ve hangi gecikmeyle açıklıyor?

## 2\. Türkiye İle Bağlantısı

Gıda fiyatlarındaki oynaklık ve "aracı kurumların" kâr marjları, Ticaret Bakanlığı, Rekabet Kurumu, Merkez Bankası ve tüketiciler için Türkiye'nin en büyük yapısal problemlerinden biridir. Bu proje, devlet kurumları için bir **Karar Destek Sistemi (DSS)**, Rekabet Kurumu için bir **Erken Uyarı Radarı** niteliği taşır. Haksız fiyat artışlarını, lokasyon bazlı spekülasyonları ve medya haberlerinin (GDELT) fiyatlar üzerindeki psikolojik etkisini gerçek veriyle kanıtlar.

## 3\. Kullanılabilecek Veri Kaynakları

Bu proje, birbirinden tamamen bağımsız formatlarda, farklı granülaritelerde ve farklı şemalarda akan verilerin entegrasyonunu gerektirir.

| Veri Kaynağı | Sağlayıcı | Erişim Yöntemi | Veri Formatı | Boyut/Hacim | Güncellenme Sıklığı |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Market Perakende Fiyatları** | marketfiyati.org.tr | API / Webhook (Arşiv) | JSON (Nested) | \~15-20 GB/ay (50K ürün x 7 market x 81 İlçe/İl) | Günlük / Intraday |
| **İBB Hal Fiyatları & Taksonomi** | İBB Açık Veri Portalı | Swagger API | REST JSON | \~2-3 GB/yıl | Günlük |
| **İzmir Hal Fiyatları** | İzmir BB Açık Veri | API & Bulk CSV | CSV / JSON | \~1 GB/yıl | Günlük |
| **İBB Hal Tonaj Verileri** | İBB Açık Veri Portalı | Bulk Download | CSV | \~500 MB (Tarihsel) | Aylık |
| **Hava Durumu (Tarım Bölgeleri)** | Open-Meteo | REST API | JSON | \~5 GB/yıl (Saatlik/Noktasal) | Saatlik (Stream) |
| **Gıda ve Tarım Haberleri** | GDELT Project | S3 Bucket / API | CSV (Zipped) | \~10-15 GB/yıl (Sadece TR) | 15 Dakikada Bir (Stream) |
| **Elektrik (Soğuk Zincir)** | EPİAŞ Şeffaflık | Şeffaflık API | JSON | \~1 GB/yıl | Saatlik (Stream) |
| **Kur & Tarım Girdi Endeksi** | TCMB EVDS | EVDS API | XML / JSON | \< 100 MB | Günlük/Aylık |

## 4\. Veri Nasıl Toplanacak (Ingestion Mimarisi & Data Engineering Zorlukları)

Bu projenin asıl mühendislik değeri **veri toplama ve uyumlaştırma (harmonization)** aşamasındadır.

### Data Engineering Zorlukları:

1. **Entity Resolution (Fuzzy Matching):** İBB Hal API'sindeki ürün tanımı `"Domates Sofralık Sera"` iken, market API'sindeki ürün slug'ı `"salkim-domates-1-kg"` şeklindedir. İki sistem arasında ID bazlı ilişki yoktur. Metin tabanlı (NLP destekli) bir eşleştirme motoru yazılması zorunludur.  
2. **Birim Standardizasyonu:** Hal'de ürünler "Kasa", "Çuval" veya "Bağ" olarak fiyatlanabilir. Markette ise "Gram", "Adet" veya "Paket"tir. Ortak bir birime (Örn: 1 KG) çevrim fonksiyonları (UDFs) geliştirilmelidir.  
3. **Temporal & Spatial Alignment:** GDELT 15 dakikalık, EPİAŞ saatlik, Hal günlük, Tonaj aylıktır. Veriler Delta Lake üzerinde "Time-series As-of Join" mantığı ile birleştirilmeli; il bazlı market verileri, o ile en yakın Hal verisiyle (Spatial join) eşleştirilmelidir.

### Ingestion Pipeline Mimarisi:

* **Real-time / Micro-batch (Kafka):** Open-Meteo (saatlik), EPİAŞ, GDELT haberleri ve `marketfiyati.org.tr`'den gelen gün içi fiyat güncellemeleri doğrudan Kafka Topic'lerine (`raw_weather`, `raw_gdelt`, `raw_market_prices`) basılır.  
* **Batch (Airflow):** İBB ve İzmir Hal API'leri her gece saat 02:00'de Airflow DAG'leri tarafından tetiklenerek çekilir. TCMB EVDS verileri ve aylık Hal Tonaj CSV'leri periyodik olarak indirilip Data Lake'e (Bronze Layer) yazılır.

## 5\. Tahmini Veri Büyüklüğü

* **Güncel ve Tarihsel Veri:** 50K perakende ürünün günlük 7 market ve seçili büyükşehirlerdeki fiyat değişimleri, 5-10 yıllık GDELT haber geçmişi ve geçmiş 10 yıllık saatlik meteoroloji verisi ile başlangıçta **50-70 GB** bandına oturacaktır.  
* **Ölçeklendirme:** Ürün geçmişi sentetik olarak veya geçmiş yıllar crawl datasıyla 81 ile yayıldığında, her gün yüz milyonlarca satır oluşacak ve proje **\~200 GB \- 500 GB** ölçeğine kolayca genişleyecektir (Big Data kriterlerini fazlasıyla karşılar).

## 6\. Realtime Veri Pipeline Nasıl Kurulabilir (Medallion Architecture)

* **Bronze Layer (Raw):** Kafka'dan okunan JSON'lar ve API'lerden gelen ham veriler hiçbir yapısal değişikliğe uğramadan Delta Lake `bronze` tablolarına kaydedilir.  
* **Silver Layer (Cleansed & Conformed):** **Apache Flink** veya **Spark Structured Streaming** devreye girer.  
  * Fiyatlardaki null değerler temizlenir.  
  * Entity Resolution uygulanır (Hal ID ile Market Slug eşleştirilir).  
  * Birimler ortak formata (KG) çevrilir.  
  * Stream üzerinden gelen saatlik don/aşırı yağış uyarıları flag'lenir.  
* **Gold Layer (Aggregated for Business):**  
  * `daily_margin_by_city_and_market`: İl, Market ve Ürün bazında Hal ve Perakende arasındaki oransal uçurum.  
  * `shock_propagation_index`: Hava durumu şoku sonrası Hal'deki fiyat artışının markete yansıma gecikme süresi (gün).

## 7\. Machine Learning Nerede Kullanılabilir? (Opsiyonel / Destekleyici)

Projenin ana odağı ML olmamakla birlikte, pipeline içine şu modeller gömülebilir:

1. **Entity Resolution için TF-IDF & Cosine Similarity:** Hal ürün listesi ile market ürün isimlerini eşleştirmek için basit ama etkili bir NLP pipeline (Spark MLlib ile).  
2. **Anomaly Detection (Isolation Forest):** Veri akışı sırasında, hal fiyatı sabitken market fiyatında aniden %50'lik mantıksız bir sıçrama (veri hatası veya spekülatif fiyatlama) saptamak için stream üzerinde çalışan basit bir anomali tespit modeli.

## 8\. Dashboard / Görselleştirme Fikri

**Superset veya Grafana** üzerinde 3 ana sekme tasarlanır:

1. **Türkiye Marj Haritası (Geo-Dashboard):** Türkiye haritası üzerinde, seçilen ürünün (örn: Domates) il bazında Hal'den Markete geçişteki kâr/maliyet marjı ısı haritası (Heatmap).  
2. **Geçişkenlik Radarı (Rockets & Feathers):** Çizgi grafikler üzerinde Hal Toptan fiyatı (Mavi Çizgi) ile Market Perakende fiyatının (Kırmızı Çizgi) zaman içindeki seyri. Alt panelde EPİAŞ elektrik ve TCMB kur trendi (Maliyet korelasyonu).  
3. **Şok ve Haber Etkisi (Event Overlay):** GDELT'ten çekilen "Tarımsal kriz/Don/Sel" haberlerinin yayınlandığı anlar veya Open-Meteo don olayları, fiyat grafiği üzerine dikey çizgiler (annotations) olarak eklenir. Şok sonrası fiyatın kaç günde reaksiyon verdiği izlenir.

## 9\. Önerilen Teknik Stack

Bu stack, endüstri standartlarında modern bir Data Engineering projesi olduğunu kanıtlar:

* **Message Broker:** Apache Kafka (Gerçek zamanlı hava, elektrik, market fiyat güncellemeleri ve haber akışı için)  
* **Stream Processing:** Apache Flink (Gerçek zamanlı entity resolution, birim dönüşümü ve anomali tespiti için)  
* **Data Lakehouse / Storage:** Delta Lake (MinIO veya AWS S3 üzerinde \- Medallion mimarisiyle Bronze/Silver/Gold katmanları)  
* **Batch / Orchestration:** Apache Airflow (İBB/İzmir Hal API'leri, TCMB veri çekimleri ve günlük Data Quality check'leri için)  
* **Query Engine:** Trino (Presto) (Delta Lake üzerindeki verileri dashboard'a sunmak için SQL motoru)  
* **Visualization:** Apache Superset (İl bazlı haritalar, zaman serisi analizleri ve marj dashboard'ları için)  
* **Deployment:** Docker / Docker-compose (Tüm sistemin kolayca ayağa kaldırılabilmesi için)
