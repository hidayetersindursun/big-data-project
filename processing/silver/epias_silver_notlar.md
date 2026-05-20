# EPİAŞ Silver Geçişi — Notlar

## Bronze Kaynak

- **Path**: `s3://s3-bbuckett/bronze/epias/`
- **Yapı**: `{dataset_adı}/year={yıl}/month={ay}/part-0000.parquet`
- **Toplam dosya**: 1.731 parquet
- **Toplam boyut**: ~41.4 MB
- **Dataset sayısı**: 26

---

## Ortak Bronze Şeması

Her 26 datasette ingestion tarafından eklenen **3 meta kolon** bulunur:

| Kolon | Tip | Değer | Silver'da |
|---|---|---|---|
| `_dataset` | string | dataset adı (`"price_and_cost"` vb.) | **Atıldı** |
| `_source` | string | `"epias"` (sabit) | **Atıldı** |
| `_ingested_at` | string | ingestion zamanı UTC | **Atıldı** |
| `year` | int | yıl (partition) | **Korundu** |
| `month` | int | ay (partition) | **Korundu** |

`_source` zaten `"epias"` sabit değerini taşıdığından atılır; silver'da `source = "epias"` olarak yeniden eklenir (standart şema gereği).

---

## Silver'da Yapılan Ortak Dönüşümler

1. `timestamp` (ISO-8601 string, `+03:00` offset'li) → `TIMESTAMP` cast
2. `_dataset`, `_source`, `_ingested_at` atıldı
3. `source = "epias"` sabit kolonu eklendi
4. `timestamp IS NULL` satırları atıldı
5. `year` / `month` partition olarak korundu

---

## Dataset Kataloğu ve Bronze Kolonları

### Fiyat Grubu

#### `price_and_cost`
Saatlik PTF, SMF, dengesizlik ve WAP verileri.

| Bronze Kolon | Tip | Silver'da |
|---|---|---|
| `timestamp` | string | → `TIMESTAMP` |
| `contract` | string | korundu |
| `mcp` | double | korundu (PTF, TL/MWh) |
| `wap` | double | korundu (ağırlıklı ort. fiyat) |
| `smp` | double | korundu (SMF) |
| `pos_imb_price` | double | korundu |
| `neg_imb_price` | double | korundu |
| `system_direction` | string | korundu (`"Enerji Açığı"` / `"Enerji Fazlası"`) |
| `sd_sign` | int | korundu (-1 / +1) |
| `pos_imb_cost` | double | korundu |
| `neg_imb_cost` | double | korundu |
| `kupst_cost` | double | korundu |

**Gold'da kullanım**: `shock_propagation_index` — elektrik fiyatı şokları ile gıda fiyatı hareketi arasındaki korelasyon. `mcp` ve `smp` temel sinyallerdir.

---

#### `mcp_smp_imbalance` ⚠️ Schema Evolution
Saatlik dengesizlik miktarları.

| Bronze Kolon | Tip | Silver'da |
|---|---|---|
| `timestamp` | string | → `TIMESTAMP` |
| `positiveImbalance` | **int↔double** | double'a merge edildi |
| `negativeImbalance` | double | korundu |
| `netImbalance` | double | korundu |

**Schema evolution**: `positiveImbalance` kolonu 2019 öncesi dosyalarda `int`, sonrasında `double` olarak yazılmış. `mergeSchema=true` + `enableVectorizedReader=false` ile çözüldü.

---

#### `zero_balance_adjustment` ⚠️ Schema Evolution
Sıfır bakiye düzeltme tutarları.

| Bronze Kolon | Tip | Silver'da |
|---|---|---|
| `timestamp` | string | → `TIMESTAMP` |
| `renewableImbalance` | **double↔int64** | double'a merge edildi |
| diğer kolonlar | double | korundu |

---

### Üretim / Tüketim Grubu

#### `real_time_generation`
Saatlik kaynak bazlı gerçek zamanlı üretim (MWh).

| Bronze Kolon | Tip | Açıklama |
|---|---|---|
| `total` | double | toplam üretim |
| `naturalGas` | double | doğalgaz |
| `dammedHydro` | double | barajlı hidro |
| `lignite` | double | linyit |
| `river` | double | nehir tipi hidro |
| `importCoal` | double | ithal kömür |
| `wind` | double | rüzgar |
| `sun` | double | güneş |
| `fueloil` | double | fuel oil |
| `geothermal` | double | jeotermal |
| `asphaltiteCoal` | double | asfaltit kömür |
| `blackCoal` | double | taş kömürü |
| `biomass` | double | biyokütle |
| `naphta` | double | nafta |
| `lng` | double | LNG |
| `importExport` | double | net ithalat/ihracat |
| `wasteheat` | double | atık ısı |

Tüm kolon isimleri `camelCase` olarak korundu — `snake_case`'e çevrilmedi, çünkü ingestion kodu aynı isimleri kullanıyor ve Gold join'larında karışıklık çıkarabilir.

---

#### `realtime_consumption`
Saatlik gerçek zamanlı tüketim.

| Bronze Kolon | Tip | Silver'da |
|---|---|---|
| `timestamp` | string | → `TIMESTAMP` |
| `time` | string | korundu (aynı saatin `HH:mm` string'i — fazlalık ama atılmadı) |
| `consumption` | double | korundu (MWh) |

**Not**: `time` kolonu `timestamp`'in tekrarıdır (`HH:mm` formatında). Gold'da kullanılmaz ama atılmadı — bronze'a sadakat.

---

#### `consumption`
Yük tahmini, UECM ve gerçek tüketim (birleşik).

| Bronze Kolon | Tip | Silver'da |
|---|---|---|
| `timestamp` | string | → `TIMESTAMP` |
| `load_plan` | double | yük tahmini (MWh) |
| `uecm` | double | uzlaştırmaya esas tüketim |
| `rt_cons` | double | gerçek zamanlı tüketim |
| `consumption` | double | uzlaştırılmış tüketim |
| `contract` | string | kontrat kodu |

---

#### `kgup` ⚠️ Schema Evolution
Kesinleşmiş üretim planı — kaynak bazlı.

Kolon isimleri Türkçe (`linyit`, `dogalgaz`, `tasKomur` vb.).

**Schema evolution**: `tasKomur` 2025 öncesinde `bigint`, sonrasında `double`. `mergeSchema=true` ile çözüldü.

---

#### `injection_quantity`
Uzlaşma esas veriş miktarı (UEVM) — kaynak bazlı (MWh).

Kolonlar: `total`, `naturalGas`, `dam`, `lignite`, `river`, `importedCoal`, `sun`, `wind`, `fueloil`, `geothermal`, `asphaltite`, `stoneCoal`, `biomass`, `naphtha`, `lng`, `internationalImport`, `internationalExport`, `other`.

---

### Yenilenebilir Enerji Grubu

#### `renewable_realtime_generation` ⚠️ Schema Evolution
YEKDEM kapsamı gerçek zamanlı üretim. Kolon isimleri Türkçe.

**Schema evolution**: `gunes` kolonu eski dosyalarda `bigint`, yenilerde `double`. `mergeSchema=true` ile çözüldü.

---

#### `renewable_injection_quantity`
YEKDEM UEVM — Türkçe kolonlar: `toplam`, `ruzgar`, `jeotermal`, `rezervuarli`, `kanalTipi`, `nehirTipi`, `copGazi`, `biyogaz`, `gunes`, `biyokutle`, `diger`.

---

#### `wind_forecast`
Rüzgar üretim tahmini.

| Bronze Kolon | Açıklama |
|---|---|
| `quarter1-4` | 15'er dakikalık çeyrek dönem üretimi |
| `generation` | gerçekleşen üretim |
| `forecast` | tahmin |

---

#### `renewable_unit_cost`
YEKDEM birim maliyeti (aylık).

| Bronze Kolon | Açıklama |
|---|---|
| `version` | hesaplama versiyonu (timestamp) |
| `supplierUnitCost` | tedarikçi birim maliyeti |
| `unitCost` | YEKDEM birim maliyeti |
| `ptf` | o dönem PTF |

---

#### `renewable_total_cost`
YEKDEM toplam giderleri — kaynak bazlı Türkçe kolonlar.

---

### Piyasa Hacmi Grubu

#### `dam_volume`
Gün öncesi piyasa hacmi.

| Bronze Kolon | Açıklama |
|---|---|
| `volumeOfAsk` | alış teklif hacmi (MWh) |

---

#### `intraday_market`
Gün içi piyasa işlemleri.

| Bronze Kolon | Açıklama |
|---|---|
| `kontratTuru` | `"Saatlik"` / `"Blok"` |
| `kontratAdi` | kontrat kodu |
| `clearingQuantityAsk` | eşleşen alış miktarı |
| `clearingQuantityBid` | eşleşen satış miktarı |
| `tradingVolume` | işlem hacmi (TL) |

---

#### `primary_frequency_capacity` / `secondary_frequency_capacity`
Frekans rezerv kapasitesi — saat bazlı.

| Bronze Kolon | Açıklama |
|---|---|
| `amount` | rezerv miktarı (MW) |
| `price` | rezerv fiyatı (TL/MW) |

---

#### `transmission_loss_factor`
İletim sistemi kayıp katsayısı.

| Bronze Kolon | Açıklama |
|---|---|
| `firstVersionValue` | ilk hesaplanan ISKK |
| `lastVersionValue` | son revize ISKK |
| `difference` | revizyon farkı |

---

### Baraj Grubu

#### `dam_daily_level`
Günlük baraj kot seviyesi.

| Bronze Kolon | Açıklama |
|---|---|
| `basin` | havza adı |
| `dam` | baraj adı |
| `dailyKot` | günlük kot (metre) |
| `damId` | baraj ID |

---

#### `dam_active_fullness`
Günlük aktif doluluk oranı.

| Bronze Kolon | Açıklama |
|---|---|
| `basin` / `dam` | havza / baraj |
| `activeFullnessAmount` | doluluk (%) |
| `id` / `damId` | kayıt / baraj ID |

---

#### `dam_active_volume`
Günlük aktif su hacmi.

| Bronze Kolon | Açıklama |
|---|---|
| `basinName` / `damName` | havza / baraj (farklı isim — diğer dam datasetlerinden tutarsız) |
| `activeVolume` | aktif hacim (hm³) |
| `id` / `damId` | kayıt / baraj ID |

**Not**: `dam_active_volume`'da kolon adları `basinName`/`damName` — diğer baraj datasetlerindeki `basin`/`dam`'dan farklı. Gold join'ında dikkat.

---

### Doğalgaz Grubu

#### `natural_gas_spot`
Spot doğalgaz piyasası fiyatları.

| Bronze Kolon | Açıklama |
|---|---|
| `dayAheadPrice` | bir gün öncesi fiyat |
| `intraDayPrice` | gün içi fiyat |
| `dayAfterPrice` | bir gün sonrası fiyat |
| `weightedAverage` | ağırlıklı ortalama |

**Gold'da kullanım**: Doğalgaz fiyatı → elektrik fiyatı → ulaşım maliyeti → gıda fiyatı zincirindeki gecikmeli etki analizi.

---

#### `natural_gas_balancing`
Dengeleme gazı alım/satım miktarları.

---

#### `natural_gas_daily_transmission`
Günlük gaz iletim verileri.

| Bronze Kolon | Açıklama |
|---|---|
| `injection` | şebekeye enjeksiyon (sm³) |
| `reproduction` | gaz üretimi (sm³) |

---

### Kesinti Grubu

#### `planned_outages`
Planlı elektrik kesintileri.

| Bronze Kolon | Silver'da |
|---|---|
| `province` | korundu (büyük harf — `"İSTANBUL-AVRUPA"` formatı) |
| `district` | korundu |
| `distributionCompanyName` | korundu |
| `endTime` | korundu (string, ISO-8601) |
| `reason` | korundu |
| `effectedNeighbourhoods` | korundu |
| `effectedSubscribers` | korundu |
| `hourlyLoadAvg` | korundu |
| `id` | korundu |

**Gold'da kullanım**: Kesinti lokasyonunu ile hal/market fiyat spike'larının örtüşmesi — spekülatif fiyatlandırma analizi.

---

#### `unplanned_outages` ⚠️ Schema Evolution
Planlı kesintilerle aynı şema.

**Schema evolution**: `hourlyLoadAvg` eski dosyalarda `bigint`, yenilerde `double`. `mergeSchema=true` ile çözüldü.

---

## Schema Evolution Sorunu — Teknik Özet

5 datasette aynı kolon farklı dönemlerde farklı numerik tip olarak kaydedilmiş (EPİAŞ API değişimleri ingestion'a yansımış):

| Dataset | Kolon | Eski tip | Yeni tip |
|---|---|---|---|
| `mcp_smp_imbalance` | `positiveImbalance` | `int` | `double` |
| `zero_balance_adjustment` | `renewableImbalance` | `double` | `int64` |
| `kgup` | `tasKomur` | `bigint` | `double` |
| `renewable_realtime_generation` | `gunes` | `bigint` | `double` |
| `unplanned_outages` | `hourlyLoadAvg` | `bigint` | `double` |

**Çözüm**: `mergeSchema=true` tüm dosyaları tarayarak en geniş uyumlu tipi seçer. Spark'ın vectorized reader'ı bu tür tip uyumsuzluklarını reddeder, bu yüzden `enableVectorizedReader=false` gerekir. Bu 5 dataset için okuma tamamlandıktan hemen sonra vectorized reader yeniden açılır.

**Bu sorunu ingestion'da düzeltmek anlamsız** — API zaman içinde tip değiştirmişse tarihsel veri bu şekilde kalmaya devam eder. Silver'da handle etmek doğru yaklaşım.

---

## Partition Stratejisi

- Bronzdaki `year` / `month` partition korunur — yeniden hesaplanmaz
- Her dataset kendi alt klasörüne gider: `silver/epias/{dataset}/year=/month=/`
- Write mode: `overwrite` — tam yeniden işleme idempotent

---

## Süre Tahmini

41.4 MB veri, local Spark ile toplam **10-20 dakika**. 5 schema evolution dataseti non-vectorized reader kullandığı için biraz daha yavaş, fakat veri küçük olduğu için fark edilmez.

---

## Çalıştırma

```bash
# Tüm 26 dataset
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/epias_silver.py

# Tek dataset (test veya yeniden çekme)
... spark-submit ... processing/silver/epias_silver.py --dataset price_and_cost
```

---

## Gold'a Geçiş İçin Notlar

- **`price_and_cost.mcp`**: Elektrik fiyatı şoklarının ana sinyali
- **`real_time_generation`**: Üretim mix'i — yenilenebilir payı arttıkça fiyat volatilitesi değişir
- **`natural_gas_spot`**: Doğalgaz → üretim maliyeti → elektrik → lojistik zinciri
- **`planned_outages` + `unplanned_outages`**: Kesinti lokasyonları ile fiyat spike'larını coğrafi olarak örtüştürmek için
- **Baraj grubu**: Hidro üretim kapasitesi → yüksek baraj = düşük MCR baskısı
- **`dam_active_volume`** farklı kolon adı kullanıyor (`basinName`/`damName`) — diğer baraj tabloları `basin`/`dam` kullanıyor. Gold'da birleştirilecekse alias gerekir.
- TCMB ve EPİAŞ timestamp granülitesi farklı: TCMB aylık, EPİAŞ saatlik — as-of join ile birleştirilecek
