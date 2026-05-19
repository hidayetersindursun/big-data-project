# Hal Sentetik Fiyat Verisi — Dokümantasyon

## Genel Bakış

Türkiye'nin 81 ili için 2016–2026 yılları arasında **günlük hal fiyat verisi** içeren veri setidir.  
Gerçek referans verisi mevcut olan şehir-yıl kombinasyonlarında **normalize edilmiş gerçek veri**, 
geri kalanında **sentetik üretilmiş veri** bulunur.

---

## Klasör ve Dosya Yapısı

```
sentetik/
├── Adana/
│   ├── 2016.csv   ← sentetik (gerçek veri 2019'dan itibaren)
│   ├── 2017.csv   ← sentetik
│   ├── 2018.csv   ← sentetik
│   ├── 2019.csv   ← GERÇEK VERİ (normalize)
│   ├── ...
│   └── 2026.csv   ← GERÇEK VERİ (normalize)
├── Ankara/
│   └── 2016.csv – 2026.csv  (tamamı sentetik)
├── Bursa/
│   └── 2016.csv – 2026.csv  (tamamı gerçek veri)
├── ...
└── Zonguldak/
    └── 2016.csv – 2026.csv  (tamamı sentetik)
```

**Toplam:** 81 il × 11 yıl = **891 dosya** | ~19 milyon satır | ~1 GB

---

## CSV Şeması

Tüm dosyalar (gerçek ve sentetik) aynı şemayı paylaşır:

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `tarih` | `YYYY-MM-DD` | Fiyatın ait olduğu gün |
| `sehir` | `string` | İl adı (Türkçe, tam adıyla) |
| `urun` | `string` | Ürün adı |
| `kategori` | `string` | `Meyve` veya `Sebze` (gerçek veride boş olabilir) |
| `en_dusuk` | `float` | Günlük en düşük fiyat (TL/kg) |
| `en_yuksek` | `float` | Günlük en yüksek fiyat (TL/kg) |
| `veri_turu` | `string` | `gercek` veya `sentetik` |

### Örnek Satırlar

```
tarih,sehir,urun,kategori,en_dusuk,en_yuksek,veri_turu
2016-01-01,Tokat,Domates,Sebze,2.9,6.14,sentetik
2016-01-02,Bursa,Armut (Deveci),Meyve,2.0,3.5,gercek
2019-09-18,Adana,HAVUÇ (Sarı Takoz),,1.5,2.5,gercek
```

> **Not:** Gerçek veri dosyalarında `kategori` sütunu bazı şehirlerde boş gelebilir
> (orijinal kaynak dosyasında bu bilgi yoksa).  
> `en_dusuk` her zaman `en_yuksek`'ten küçük veya eşittir (ters kayıtlar düzeltilmiştir).

---

## Gerçek Veri Kaynakları

Aşağıdaki şehirler için belirtilen yıllarda normalize edilmiş **gerçek hal verisi** bulunur.
Bu veriler `hal/referans/` klasöründeki orijinal dosyalardan üretilmiştir; orijinaller değiştirilmemiştir.

| Şehir | Gerçek Veri Yılları | Sentetik Yıllar |
|-------|---------------------|-----------------|
| Bursa | 2016 – 2026 | — |
| İstanbul | 2016 – 2026 | — |
| İzmir | 2016 – 2026 | — |
| Gaziantep | 2016 – 2026 | — |
| Konya | 2016 – 2026 | — |
| Adana | 2019 – 2026 | 2016 – 2018 |
| Manisa | 2020 – 2026 | 2016 – 2019 |
| Antalya | 2021 – 2026 | 2016 – 2020 |
| Kocaeli | 2021 – 2026 | 2016 – 2020 |
| Tekirdağ | 2021 – 2026 | 2016 – 2020 |
| Diğer 71 il | — | 2016 – 2026 (tamamı) |

---

## Sentetik Veri Üretim Metodolojisi

Sentetik fiyat şu 4 faktörün çarpımından oluşur:

```
fiyat = baz_fiyat × enflasyon_carpani × konum_carpani × mevsim_carpani × gurultu
```

### 1. Baz Fiyat (2026 İstanbul Çapası)

Her ürün için 2026 yılı İstanbul gerçek hal verisinden çıkarılan TL/kg değerleri.

| Ürün | Baz En Düşük (TL) | Baz En Yüksek (TL) |
|------|-------------------|---------------------|
| Domates | 54,00 | 121,00 |
| Patates | 10,00 | 20,00 |
| Elma (Golden) | 25,00 | 55,00 |
| Sarımsak (Kuru) | 60,00 | 140,00 |
| Kiraz | 55,00 | 130,00 |
| Mantar (Kültür) | 85,00 | 130,00 |

### 2. Enflasyon Çarpanı

Bursa, İstanbul, İzmir ve Konya gerçek hal verilerindeki **yıllık medyan fiyat** değerleri
baz alınarak hesaplanan kümülatif fiyat endeksi.  
Gıda ürünlerindeki fiyat artışı genel TÜFE'den yaklaşık 1,5 kat daha hızlı gerçekleşmiştir.

| Yıl | Fiyat Endeksi (2016=1,0) | Çarpan (2026 baz) |
|-----|--------------------------|-------------------|
| 2016 | 1,0000 | 0,0380 |
| 2017 | 1,2054 | 0,0458 |
| 2018 | 1,4018 | 0,0532 |
| 2019 | 1,7232 | 0,0654 |
| 2020 | 1,7679 | 0,0671 |
| 2021 | 2,0982 | 0,0797 |
| 2022 | 4,3750 | 0,1661 |
| 2023 | 7,6786 | 0,2915 |
| 2024 | 12,500 | 0,4746 |
| 2025 | 17,411 | 0,6610 |
| 2026 | 26,339 | 1,0000 |

> 2016→2026 arasında gıda fiyatları ortalama **~26,3 kat** artmıştır.

### 3. Konum Çarpanı

Şehirin coğrafi konumuna ve üretim merkezlerine uzaklığına göre belirlenir.

| Bölge | Sebze | Meyve | Mantık |
|-------|-------|-------|--------|
| Akdeniz (Antalya, Adana, Mersin) | × 0,78–0,82 | × 0,85–0,88 | Üretim merkezi, seracılık |
| Ege (İzmir, Manisa, Aydın) | × 0,85–0,88 | × 0,87–0,90 | Yoğun tarım |
| Marmara (İstanbul, Bursa, Kocaeli) | × 0,95–1,00 | × 0,95–1,00 | Referans |
| Güneydoğu (Gaziantep, Şanlıurfa) | × 0,85–0,90 | × 0,90–0,95 | Yakın üretim |
| İç Anadolu (Ankara, Kayseri) | × 1,05 | × 1,08 | Nakliye maliyeti |
| Karadeniz (Trabzon, Artvin, Rize) | × 1,05–1,12 | × 0,95–1,08 | Engebeli arazi |
| Doğu Anadolu (Erzurum, Van, Ağrı) | × 1,18–1,22 | × 1,20–1,25 | Uzak konum, iklim |

### 4. Mevsimsel Çarpan

Her ürün grubu için hasat takvimine dayalı aylık çarpan (1,0 = ortalama).

| Ürün grubu | En Ucuz Dönem | En Pahalı Dönem |
|------------|---------------|-----------------|
| Domates, Patlıcan, Biber | Temmuz (×0,65) | Ocak (×1,30) |
| Karpuz, Kavun | Temmuz (×0,58) | Ocak–Şubat (×1,50) |
| Çilek | Mayıs–Haziran (×0,70) | Aralık–Ocak (×1,50) |
| Kiraz | Mayıs–Haziran (×0,80) | Kış (×1,50) |
| Portakal, Mandalina | Aralık–Ocak (×0,80) | Temmuz (×1,25–1,45) |
| Üzüm | Temmuz–Ağustos (×0,68) | Kış (×1,50) |
| Elma, Armut | Ekim–Kasım (×0,78) | Temmuz (×1,18) |

### 5. Günlük Gürültü

Gerçek piyasadaki günlük dalgalanmayı temsil etmek amacıyla `±%4` rastgele sapma eklenir.  
Tekrar üretilebilirlik için sabit tohum (`seed=42`) kullanılmaktadır.

---

## Standart Ürün Listesi (Sentetik Dosyalar)

Sentetik verisi olan tüm şehir-yıllarda aşağıdaki 59 ürün bulunur.  
Gerçek veri dosyalarında ürün sayısı ve isimlendirme kaynak hale göre değişebilir.

### Sebzeler (36 adet)

| | | | |
|--|--|--|--|
| Domates | Domates (Cherry) | Biber (Sivri) | Biber (Dolmalık) |
| Biber (Çarliston) | Biber Kapya | Patlıcan | Kabak |
| Salatalık | Patates | Soğan (Kırmızı) | Soğan (Beyaz) |
| Yeşil Soğan | Sarımsak (Kuru) | Havuç | Lahana (Beyaz) |
| Lahana (Kırmızı) | Marul (Aysberg) | Marul (Kıvırcık) | Marul (Düz) |
| Ispanak | Maydanoz | Roka | Nane |
| Tere | Dereotu | Fasulye (Taze) | Bezelye |
| Bakla (Taze) | Karnabahar | Brokoli | Kereviz |
| Pırasa | Pancar | Mantar (Kültür) | Semizotu |

### Meyveler (23 adet)

| | | | |
|--|--|--|--|
| Elma (Golden) | Elma (Starking) | Elma (Granny Smith) | Armut (Deveci) |
| Armut (Santamaria) | Portakal | Portakal (Sıkmalık) | Mandalina |
| Limon | Greyfurt | Muz (Yerli) | Üzüm (Beyaz) |
| Karpuz | Kavun | Çilek | Kiraz |
| Şeftali | Kayısı | Erik | Nar |
| Ayva | Kivi | Yeni Dünya (Malta) | |

---

## Üretim Scripti

| Dosya | Açıklama |
|-------|----------|
| `hal/sentetik_uret_v2.py` | Ana üretim scripti — gerçek veri normalizer + sentetik üretici |
| `hal/sentetik_uret.py` | İlk versiyon (parquet, 19 şehir) — referans |

Veriyi yeniden üretmek için:

```bash
cd hal/
python sentetik_uret_v2.py
```

---

## Kısıtlamalar ve Notlar

- Gerçek veri dosyalarında **ürün isimlendirmesi standardize edilmemiştir**; kaynak halin
  kullandığı adlar korunmuştur (`HAVUÇ (Sarı Takoz)`, `Marul K.` gibi).
- Gerçek veri **her zaman 1 Ocak'tan başlamayabilir**; kaynak halinin kayıt başlangıcına bağlıdır
  (ör. Adana 2019 → 18 Eylül 2019'dan itibaren).
- Sentetik verinin gerçek veriye göre ortalama sapması **±%25** civarındadır —
  bölgesel fiyat dinamikleri, nadir ürünler ve piyasa şokları modellenmemiştir.
- 2026 yılı gerçek dosyaları üretim tarihine kadar olan veriyi içerir (Mayıs 2026'ya kadar);
  gerisi sentetik ile tamamlanmamıştır — sadece gerçek veri bulunur.
