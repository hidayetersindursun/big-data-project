SUNUM TAMAMEN İNGİLİZCE OLACAK. BİR SAYFADA DA EKİP ÜYELERİNİ TANIT. İSİMLER: AZMİ YAĞLI, ABDULLAH ZENGİN, HİDAYET ERSİN DURSUN

### Slayt 1: Problem Statement (İş Problemi)
**Kullanılacak Prompt:**
> "Bir sunumun 'Problem Statement' (İş Problemi) slaytı için içerik hazırla. Konu: Türkiye'deki gıda tedarik zinciri şeffaflıksızlığı ve tarladan markete oluşan anlamsız fiyat marjları. Slaytta 3 ana vurgu olmalı: 1) Sistematik veri eksikliği yüzünden bu sorunun bir 'kara kutu' olması. 2) Asimetrik fiyat geçişkenliği ('Rockets and Feathers' etkisi - maliyet artarken fiyatın roket gibi çıkıp, düşerken tüy gibi inmesi). 3) Lokasyon bazlı spekülasyonlar (Aynı hal giriş fiyatına sahip ürünün farklı ilçelerde farklı fiyatlanması). Lütfen slayt başlığı, 3 çarpıcı madde (bullet point) ve benim 1 dakika içinde anlatabileceğim akıcı bir 'Sunucu Notu' (Speaker Notes) yaz. Slaytın görsel fikri için de kısa bir betimleme ekle."

### Slayt 2: Goal (Projenin Amacı ve Çözüm)
**Kullanılacak Prompt:**
> "Bir sunumun 'Goal' (Hedef/Çözüm) slaytı için içerik hazırla. Slaytın amacı, bahsettiğimiz tedarik zinciri problemine veri mühendisliği ve veri bilimi ile nasıl bir çözüm getirdiğimizi anlatmak. Ana hedefimiz: Devlet kurumları (Ticaret Bakanlığı, Rekabet Kurumu) ve paydaşlar için bir 'Karar Destek Sistemi (DSS)' ve 'Erken Uyarı Radarı' inşa etmek. Gerçek zamanlı hava durumu şoklarını, hal fiyatlarını ve market fiyatlarını entegre eden bir motor yaratıyoruz. Slayt için güçlü bir vizyon cümlesi, 4 maddelik projenin ana çıktıları (İl bazlı marj analizi, Şok yayılım ölçümü vs.) ve 1 dakikalık etkili bir 'Sunucu Notu' yaz. Slayt tasarım fikri olarak veriden-içgörüye giden bir huni veya köprü metaforu öner."

### Slayt 3: Data (Veri Kaynakları ve Hacim)
**Kullanılacak Prompt:**
> "Bir sunumun 'Data' (Veri Kaynakları) slaytı için içerik hazırla. Hedef kitlem veri analistleri, mühendisleri ve yöneticiler. Bu slaytta birbirinden tamamen bağımsız 8 farklı veri kaynağını (Market API'leri, İBB/İzmir Hal API'leri, Open-Meteo, GDELT haberleri, EPİAŞ elektrik, TCMB) nasıl entegre ettiğimizi göstermeliyiz. Slaytta bir tablo veya infografik kurgusu yarat: Kaynaklar, Veri Formatları (REST JSON, CSV, Stream) ve Güncellenme Sıklığı (15 dk, Saatlik, Günlük). Ayrıca projenin şu an 50-70 GB olduğunu ama kolayca 500 GB ölçeğine çıkabileceğini (Big Data) vurgula. 1.5 dakikalık sunucu notu ekle."

### Slayt 4: Data Types & Engineering Challenges (Veri Tipleri ve Mimari Zorluklar)
**Kullanılacak Prompt:**
> "Bir sunumun 'Data Types & Engineering Challenges' slaytı için içerik hazırla. Bu slayt 'Data Engineering' şapkamı göstereceğim yer. Medallion mimarisini (Bronze, Silver, Gold), Kafka ile streaming, Airflow ile batch orchestration yaptığımızı anlat. Slaytın odak noktası 3 büyük mühendislik zorluğu olmalı: 1) Entity Resolution (Fuzzy Matching ile Hal'deki 'Domates Sofralık Sera' ile Marketteki 'salkim-domates'i eşleştirme). 2) Birim Standardizasyonu (Kasa/Çuval'dan KG'a çevrim). 3) Temporal & Spatial Alignment (Farklı zaman dilimlerinde ve farklı lokasyonlarda akan veriyi Delta Lake üzerinde birleştirme). Slaytın iskeletini, kısa teknik maddeleri ve 1.5 dakikalık iddialı bir sunucu notu yaz."

### Slayt 5: Implementation Plan (Gantt Chart / Yol Haritası)
**Kullanılacak Prompt:**
> "Bu proje için 12 haftalık bir 'Implementation Plan' (Uygulama Planı) slaytı tasarla. Slaytta bir Gantt Chart mantığı olmalı. Fazları şu şekilde böl: Faz 1: Altyapı ve Ingestion (Kafka, Airflow, Bronze Layer). Faz 2: Transformation & Entity Resolution (Spark/Flink ile Silver Layer, NLP eşleştirmeleri). Faz 3: Modeling & Aggregation (Gold layer, Anomali tespiti, Spatial Join). Faz 4: Dashboard & BI (Superset entegrasyonu ve raporlama). Lütfen bu fazları ve alt görevleri bir Markdown tablosu (Gantt Chart taslağı) olarak sun. Sunum sırasında bu planı 1 dakikada nasıl özetleyebileceğime dair bir 'Sunucu Notu' ekle."

### Slayt 6: Business and Strategic Value (İş ve Stratejik Değer)
**Kullanılacak Prompt:**
> "Bir sunumun 'Business and Strategic Value' slaytı için içerik hazırla. Bu projenin Türkiye için neden kritik bir Karar Destek Sistemi olduğunu anlat. Odaklanılacak 3 kitle var: 1) Regülatörler/Devlet (Haksız fiyat artışlarını gerçek veriyle anında tespit, ceza mekanizmaları için kanıt). 2) Tüketiciler/Toplum (Şeffaflık, enflasyonist psikolojiyi anlama). 3) Ekonomik Strateji (Hangi illerde lojistik maliyet sorunu var, hangi marketler fiyat geçişkenliğinde fırsatçılık yapıyor). Vurucu bir başlık, 3 temel değer önerisi ve 1 dakikalık, yatırımcı perdesinden konuşan bir 'Sunucu Notu' hazırla."

### Slayt 7: Data Science & Dashboard (Görselleştirmeler ve Analitik - DS Şapkası)
**Kullanılacak Prompt:**
> "Bir sunumun 'Dashboard & Visualizations' slaytı için içerik hazırla. Bu slayt 'Data Scientist' şapkamı göstereceğim yer. Apache Superset veya Grafana üzerinde tasarladığım 3 ana görselleştirmeyi anlatacağım. 1) Türkiye Marj Haritası (İl bazında Hal-Market arası kâr/maliyet ısı haritası). 2) Geçişkenlik Radarı (Hal Toptan vs Market Perakende fiyatlarının zaman serisi grafiği, 'Rockets and Feathers' kanıtı). 3) Şok Etkisi Overlay (GDELT haberleri ve don/sel şoklarının fiyat grafiği üzerine eklenmesi). Her bir grafiğin işe nasıl bir içgörü kattığını açıklayan kısa metinler ve 1.5 dakikalık çok etkili bir sunucu notu yaz. Görsellerin nasıl tasarlanması gerektiğine dair prompt/açıklama da ekle."

### Slayt 8: Team Introduction (Takım ve Roller)
**Kullanılacak Prompt:**
> "Bir sunumun son slaytı olan 'Team Introduction' için içerik hazırla. Bu projede Data Engineer ve Data Scientist rollerinin entegre çalıştığını göstermek istiyorum (Eğer tek kişiysem, bu iki şapkayı nasıl taşıdığımı anlatacağım). Data Engineer'ın sorumlulukları: Pipeline inşası, Streaming (Kafka/Flink), Batch orchestration (Airflow), Medallion mimarisi. Data Scientist'in sorumlulukları: Entity Resolution için TF-IDF/NLP algoritmaları, İzolasyon Ormanı (Isolation Forest) ile anomali tespiti ve BI görselleştirmeleri. Bu rolleri net ve havalı bir şekilde ifade eden maddeler ve sunumu güçlü bir şekilde bitirecek 1 dakikalık 'Kapanış ve Teşekkür' sunucu notu hazırla."

