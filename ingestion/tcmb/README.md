# ingestion/tcmb

TCMB EVDS API üzerinden döviz, enflasyon ve maliyet sürücüsü serilerini çeken ingestion modülü.

## Dosyalar

- `tcmb_evds.py` — EVDS veri ingestion scripti
- `plot_tcmb.py` — JSONL çıktılarından interaktif HTML dashboard üretir
- `data/` — seri bazlı JSONL çıktılar ve `state.json`
- `plots/` — lokal grafik çıktıları (git'e alınmaz)

## Çalıştırma

```bash
# Sadece bayat serileri güncelle
python ingestion/tcmb/tcmb_evds.py

# Hepsini baştan çek (DEFAULT_START = 2024-01-01)
python ingestion/tcmb/tcmb_evds.py --force

# 2003'ten tam geçmiş
python ingestion/tcmb/tcmb_evds.py --force --full

# HTML dashboard üret
python ingestion/tcmb/plot_tcmb.py
```

Çıktı: `ingestion/tcmb/data/{seri_adı}.jsonl` — her satır bir gözlem (`date`, `value`, `series`)
State: `ingestion/tcmb/data/state.json`

## Seriler (21 toplam)

### Döviz Kurları — günlük (`fx_daily`)

| Seri Adı | EVDS Kodu | Açıklama |
|---|---|---|
| `usd_try_alis` | TP.DK.USD.A.YTL | USD/TRY alış |
| `usd_try_satis` | TP.DK.USD.S.YTL | USD/TRY satış |
| `eur_try_alis` | TP.DK.EUR.A.YTL | EUR/TRY alış |
| `eur_try_satis` | TP.DK.EUR.S.YTL | EUR/TRY satış |
| `gbp_try_alis` | TP.DK.GBP.A.YTL | GBP/TRY alış |

### Enflasyon — aylık YoY (`inflation_monthly`)

| Seri Adı | EVDS Kodu | Açıklama |
|---|---|---|
| `tufe_genel_yoy` | TP.FE.OKTG01 | TÜFE Genel |
| `tufe_cekirdek_yoy` | TP.FE.OKTG02 | TÜFE Çekirdek (C endeksi) |
| `tufe_islem_disi_yoy` | TP.FE.OKTG05 | TÜFE İşlem Dışı |
| `tufe_gida_yoy` | TP.FG.J0 | Yİ-ÜFE Genel |
| `yiufe_tarim_yoy` | TP.FG.J01 | Yİ-ÜFE Tarım, Ormancılık ve Balıkçılık |
| `yiufe_genel_yoy` | TP.FG.J011 | Yİ-ÜFE Tarım Alt Grubu |

### Yİ-ÜFE Sektör Alt Endeksleri — aylık YoY (`yiufe_sector_monthly`)

| Seri Adı | EVDS Kodu | Açıklama |
|---|---|---|
| `yiufe_hayvancilik_yoy` | TP.FG.J012 | Yİ-ÜFE Hayvancılık |
| `yiufe_gida_imalat_yoy` | TP.FG.J031 | Yİ-ÜFE Gıda İmalatı |
| `yiufe_icecek_imalat_yoy` | TP.FG.J032 | Yİ-ÜFE İçecek İmalatı |
| `yiufe_elektrik_gaz_yoy` | TP.FG.J04 | Yİ-ÜFE Elektrik, Gaz ve Buhar |
| `yiufe_ulastirma_yoy` | TP.FG.J07 | Yİ-ÜFE Ulaştırma |

### TÜFE Alt Grupları & Kredi Faizleri — aylık (`tufe_cost_monthly`)

| Seri Adı | EVDS Kodu | Açıklama | Formül |
|---|---|---|---|
| `tufe_gida_alkolsuz_yoy` | TP.FE.OKTG10 | TÜFE Gıda ve Alkolsüz İçecekler | YoY |
| `tufe_ulastirma_yoy` | TP.FE.OKTG07 | TÜFE Ulaştırma | YoY |
| `tufe_konut_enerji_yoy` | TP.FE.OKTG04 | TÜFE Konut, Su, Elektrik, Gaz | YoY |
| `kredi_faiz_ticari` | TP.KTF10 | Ticari kredi faiz oranı | Ham |
| `kredi_faiz_tuketici` | TP.KTF11 | Tüketici kredi faiz oranı | Ham |

## API Notları

- EVDS tek istekte ~1000 gözlem limiti uygular; script frekansa göre otomatik pencereliyor.
- Aylık seriler `freq=5`, günlük seriler `freq=1` ile çekilir.
- YoY seriler `formula=3`, ham değer seriler `formula=0` kullanır.
- `aggregationTypes` sayısal değil string olmalı (`avg`, `last` vb.) — aksi halde 400 döner.
- API anahtarı ortam değişkeniyle override edilebilir:

```bash
export EVDS_API_KEY="..."
```
