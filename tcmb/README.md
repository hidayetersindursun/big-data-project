# TCMB EVDS Veri Cekme Modulu

Bu klasor, TCMB EVDS API uzerinden doviz ve enflasyon serilerini cekmek, lokal JSONL ciktilari uretmek ve temel grafikler olusturmak icin kullanilir.

## Dosyalar

- `tcmb_evds.py`: EVDS veri ingestion scripti
- `plot_tcmb.py`: JSONL ciktilarindan interaktif HTML grafik dashboard'u uretir
- `data/`: Seri bazli JSONL ciktilar ve `state.json`
- `plots/`: Lokal grafik ciktilari (git'e alinmaz)

## Cozulen Problemler

Bu modulde veri cekme hatasi ve yavaslikla ilgili birden fazla sorun tespit edilip giderildi:

1. **Yanlis API parametre formati (400 Bad Request)**
   - `aggregationTypes=5` gibi sayisal kullanim yerine EVDS'in bekledigi string degerlere gecildi (`avg`, `last`, vb.).
   - Batch cagrilarinda `formulas` ve `aggregationTypes` parametreleri seri sayisi kadar `-` ile tekrar edilerek gonderiliyor.

2. **Aylik frekans hatasi**
   - Enflasyon batch'inde `freq=4` (ayda 2 kez) yerine `freq=5` (aylik) kullanildi.

3. **Formula/seri adi uyumsuzlugu**
   - `*_yoy` adli serilerde `formula=1` yerine `formula=3` (Yillik Yuzde Degisim) kullanildi.
   - Formula uygulandiginda EVDS kolon adinin `KOD-FORMULA` seklinde donmesini destekleyecek parsing eklendi.

4. **Asiri retry ve gecikme**
   - Uzun backoff zinciri kisaltildi.
   - 4xx hatalarda retry kapatildi (parametre hatasi oldugu icin tekrar deneme anlamsiz).

5. **Eksik tarihsel veri (API limiti kaynakli)**
   - EVDS tek istekte yaklasik 1000 gozlem limiti uyguluyor.
   - Uzun tarih araliklari frekansa gore guvenli pencerelere bolunup parca parca cekiliyor (windowing), sonra birlestiriliyor.

6. **State ve tarih parse kararliligi**
   - Gunluk (`DD-MM-YYYY`) ve aylik (`YYYY-M`) tarih formatlari birlikte parse edilip state guvenli sekilde guncelleniyor.

## Sonuc

- `--force --full` ile 2003'ten bugune veri cekimi eksiksiz calisiyor.
- Cekim suresi belirgin sekilde iyilesti.
- Aylik serilerde eksik ay yok.
- Kur serilerindeki bosluklar EVDS yayin takvimi/tatil kaynakli dogal bosluklar.

## Kullanim

### 1) Veri cek

```bash
python tcmb/tcmb_evds.py
```

Opsiyonlar:

```bash
python tcmb/tcmb_evds.py --force
python tcmb/tcmb_evds.py --force --full
python tcmb/tcmb_evds.py --discover
python tcmb/tcmb_evds.py --group <GROUP_CODE>
```

### 2) Grafik olustur

```bash
python tcmb/plot_tcmb.py
```

Cikti:

- `tcmb/plots/tcmb_dashboard.html`

## Notlar

- API anahtari varsayilan olarak kodda okunur; tercihen ortam degiskeni kullanin:

```bash
export EVDS_API_KEY="..."
```

- `tcmb/plots/` klasoru lokal calisma ciktilari oldugu icin `.gitignore` altindadir.
