# Sentetik Geçmiş Verisi Üretim Metodolojisi

## Neden Sentetik Veri?

Gerçek tarihsel market fiyatı verisi kamuya açık değil. Ancak projenin amacı büyük veri işleme kapasitesini göstermek ve pandemi öncesi/sonrası fiyat gap analizini yapabilmektir. Bu nedenle gerçek TCMB enflasyon verisi kullanılarak istatistiksel olarak tutarlı geçmiş verisi üretilmiştir.

---

## Metodoloji

Sentetik fiyat şu 4 bileşenin çarpımıyla hesaplanır:

```
sentetik_fiyat = baz_fiyat × deflasyon × mevsim_düzeltmesi × günlük_gürültü
```

### 1. Baz Fiyat

Gerçek scrape'den alınan en güncel market fiyatı (2026-05-17 tarihi). Her ürün, ilçe ve market (depot) için ayrı baz fiyat kullanılır.

### 2. Deflasyon Faktörü

**Kaynak:** TCMB EVDS — Taze Meyve-Sebze Fiyat Endeksi (kod: `TP.FE.OKTG11`)

Aylık YoY (yıllık yüzde değişim) verisi 2003'ten bugüne indirilmiştir. Bu veriden her yıl için ortalama yıllık enflasyon oranı hesaplanmış, ardından günlük bileşik oran elde edilmiştir:

```
günlük_oran = yıllık_oran / 365
deflasyon = 1 / ∏(1 + günlük_oran)   [baz tarihten hedef tarihe kadar]
```

**Örnek yıllık oranlar (TCMB verisinden):**

| Yıl  | Taze Meyve-Sebze Enflasyonu |
|------|----------------------------|
| 2020 | ~%20                       |
| 2021 | ~%35                       |
| 2022 | ~%93 (zirve)               |
| 2023 | ~%72                       |
| 2024 | ~%45                       |
| 2025 | ~%30                       |

Bu serinin genel TÜFE'den farklı davrandığı dönemler vardır — meyve-sebze fiyatları iklim ve hasat koşullarına bağlı olarak çok daha volatil seyreder.

### 3. Ürün Bazlı Mevsimsel Düzeltme

Her ürünün kendi hasat takvimi vardır. **Kaynak:** [Gıda Kurtarma Derneği Mevsim Rehberi](https://gktd.org/1027-2/) — Türkiye'ye özgü tarım takvimi.

```
mevsim_düzeltmesi = profil[hedef_ay] / profil[baz_ay]
```

Her ürün için mevsim aylarında **0.80** (hasat → ucuz), mevsim dışında **1.25** (kıtlık → pahalı), geçiş aylarında **1.00** çarpanı uygulanır.

| Ürün Grubu         | Ucuz Aylar (hasat) | Pahalı Aylar     |
|--------------------|-------------------|------------------|
| Domates            | Tem–Ekim          | Kasım–Mayıs      |
| Mandalina          | Oca–Şub, Kas–Ara  | Nis–Eyl          |
| Çilek              | Nis–Haz           | Tem–Mar          |
| Karpuz/Kavun       | Tem–Eyl           | Ekim–Haz         |
| Ispanak/Lahana     | Oca–Mar, Kas–Ara  | Nis–Ekim         |
| Portakal           | Oca–Mar, Aralık   | Nis–Kas          |
| Elma/Armut         | Oca–Mar, Eki–Ara  | Nis–Eyl          |

46 ürün/ürün grubu için ayrı profil tanımlanmıştır. Eşleşme yoksa genel meyve-sebze mevsim eğrisi uygulanır.

### 4. Günlük Rastgele Gürültü (±%5)

Gerçek piyasada fiyatlar her gün hafifçe dalgalanır. Bu dalgalanmayı temsil etmek için ±%5 aralığında düzgün dağılımlı gürültü eklenir.

**Önemli:** Tohum (seed) olarak `hash(ürün_adı + tarih + depot_id)` kullanılır. Bu sayede:
- Her çalıştırmada **aynı sonuç** üretilir (deterministik/tekrarlanabilir)
- Farklı ürün ve marketler **birbirinden bağımsız** dalgalanır

---

## Veri Hacmi

| Süre   | Satır Sayısı | Parquet Boyutu | S3 Dosya Sayısı |
|--------|-------------|----------------|-----------------|
| 7 gün  | ~906K       | ~170 MB        | 7               |
| 1 yıl  | ~47M        | ~8.8 GB        | 365             |
| 6 yıl  | ~283M       | ~52 GB         | 2,190           |

> Her gün tüm şehir/ilçe/market kombinasyonları tek bir Parquet dosyasında birleştirilir (`bronze/market/synthetic/YYYY-MM-DD.parquet`). Spark bu yapıyı tarih bazlı partition pruning ile verimli okur.

---

## Sınırlamalar ve Şeffaflık

- Bölgesel fiyat farklılıkları modele dahil edilmemiştir (şehirler arasında mevsim farkı yok)
- GDELT haber şokları (kuraklık, don, ihracat yasağı) modele dahil edilmemiştir
- Bölgesel fiyat farklılıkları korunmuştur (her ilçe kendi baz fiyatını kullanır)
- Verinin sentetik olduğu tüm kayıtlarda `"_synthetic": true` alanıyla işaretlenmiştir

---

## Teknik Uygulama

```
ingestion/tcmb/data/tufe_taze_meyve_sebze_yoy.jsonl  ← TCMB gerçek verisi
        ↓
generate_and_upload_synthetic.py
        ↓
S3: bronze/market/synthetic/{tarih}.parquet
```

Kullanım:
```bash
python generate_and_upload_synthetic.py --bucket <bucket-adı> --days 2190
```
