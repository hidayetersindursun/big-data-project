# Harman Hal Fiyat Scraper

Harmanapps.com'dan günlük hal fiyatlarını çeken ve sentetik veri formatına uyumlu CSV üreten script.

## Çalıştırma

```bash
python harman_gunluk_hal_fiyat_scraber.py
```

Bağımlılıklar: `curl_cffi`, `beautifulsoup4`, `pandas`

## Çıktı

Her çalıştırmada o güne ait bir CSV dosyası oluşur:

```
harman_hal_fiyat_DD_MM_YYYY.csv
```

### Sütunlar

| Sütun | Tip | Açıklama |
|---|---|---|
| `tarih` | string | `YYYY-MM-DD` formatında |
| `sehir` | string | Şehir adı (harman sitesindeki isim) |
| `urun` | string | Normalize edilmiş ürün adı |
| `kategori` | string | `Sebze`, `Meyve` veya `Diğer` |
| `en_dusuk` | float | En düşük fiyat (TL/kg) |
| `en_yuksek` | float | En yüksek fiyat (TL/kg) |
| `veri_turu` | string | Her zaman `gercek` |

Sentetik veri (`sentetik/{Şehir}/{yil}.csv`) ile aynı şema.

## Kapsam

- Harmanapps'te kayıtlı şehirler (~17 şehir, güncel liste siteden dinamik çekilir)
- Şehir başına 1-5 sayfa, toplamda ~1500-2000 satır/gün

## Ürün Normalizasyonu

Ham sitedeki kirli ürün adları (`DOMATES(SALKIM)`, `Domates Salkım`, `domatessalkım` vb.) standart ada dönüştürülür. Eşleştirilemeyen ürünler `kategori=Diğer` ile olduğu gibi bırakılır.

## Notlar

- Cloudflare koruması `curl_cffi` ile aşılıyor (`impersonate="chrome110"`)
- Sayfa sonu tespiti: aynı içerik tekrar gelince durur (harmanapps son sayfayı tekrar döndürür)
- Harmanapps'in sayfa yapısı değişirse (CSS class, URL formatı) scraper güncellenmeli
