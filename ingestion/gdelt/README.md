# GDELT Veri Toplama Modülü (ingestion/gdelt)

Bu modül, Google Cloud BigQuery üzerinde barındırılan GDELT v2 GKG (Global Knowledge Graph) veri setinden Türkiye ile ilgili gıda ve ekonomi haberlerinin duygu durumu (tonalite) ve meta verilerini çeker.

## Gereksinimler

- `google-cloud-bigquery`
- `db-dtypes`
- `pandas`
- `python-dotenv`

## GCP Kimlik Doğrulama (Service Account) Ayarları

BigQuery'den sorgu atabilmek için aktif bir Google Cloud Projesine ve API yetkisine sahip bir Service Account anahtarına ihtiyacınız vardır:

1. [Google Cloud Console](https://console.cloud.google.com)'a gidin.
2. Bir proje oluşturun veya mevcut projenizi seçin.
3. **API & Services** > **Library** kısmından **BigQuery API**'yi etkinleştirin.
4. **IAM & Admin** > **Service Accounts** bölümüne gidin.
5. Yeni bir Service Account oluşturun (Rol olarak "BigQuery User" veya "BigQuery Data Viewer" verebilirsiniz).
6. Oluşturduğunuz hesaba tıklayıp **Keys** > **Add Key** > **Create new key** adımlarını takip ederek **JSON** formatında anahtarı indirin.
7. İndirdiğiniz JSON dosyasını güvenli bir konuma (örneğin proje dizini dışına veya git ignore edilmiş bir klasöre) kaydedin. Örneğin: `gcp-credentials.json`
8. Proje kök dizinindeki `.env` dosyasına aşağıdaki satırı ekleyin:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=/dosya/yolu/gcp-credentials.json
   ```

## Kullanım

Veri çekme botu varsayılan olarak son 1 günün verisini kontrol edip çeker. Önceden çekilen günleri `state.json` dosyasında tutarak mükerrer sorguların önüne geçer.

```bash
# Sadece çalışmayı test etmek için (veri kaydetmez, kotanızı harcar ama sonucu görmenizi sağlar)
python ingestion/gdelt/gdelt_ingest.py --dry-run

# Belirli bir tarih aralığını çekmek için
python ingestion/gdelt/gdelt_ingest.py --start-date 2026-05-10 --end-date 2026-05-15

# Varsayılan çalışma (dünün verisini çeker, crontab veya Airflow'da çalıştırılabilir)
python ingestion/gdelt/gdelt_ingest.py
```

## Çıktı Formatı

Betiğin başarılı çalışması sonucunda `ingestion/gdelt/data/{YYYY-MM-DD}.jsonl` dosyası oluşur. Her satır bir JSON objesidir:

```json
{
  "id": "20260515120000-12345",
  "date": "20260515120000",
  "source": "1",
  "url": "https://ornek-haber-sitesi.com/haber-adresi",
  "tone": -4.5,
  "themes": [
    "FOOD_SECURITY",
    "ECON_INFLATION",
    "WB_135_TRANSPORT"
  ],
  "_ingested_at": "2026-05-16T08:00:00.123456"
}
```

* `tone`: GDELT V2Tone metriğinin ilk değeri. Pozitif değerler olumlu, negatif değerler olumsuz haber tonunu ifade eder.
* `themes`: GKG temalarının ayrıştırılmış listesidir.

**Not:** BigQuery'deki GDELT sorguları kotadan harcar. Ücretsiz sınır ayda 1 TB'dır. Bu nedenle geriye dönük yüklü veri çekimi yaparken `start-date` ve `end-date` filtrelerini birer haftalık/aylık bloklar halinde dikkatlice kullanınız.

## Veri Çekme Sıklığı ve Optimizasyon

Proje canlı veriyi 15 dakikada bir çekebilecek kapasitede tasarlandı, ancak bulut maliyet optimizasyonu ve tarım ürünleri fiyatlarının günlük/haftalık değişmesi gerçeği (Business Logic) göz önüne alınarak veri akışı Airflow ile günde 1 kez Batch Ingestion yapacak şekilde ayarlandı.

## GDELT Bize Ne Sağlar? (Verinin Kapsamı ve Amacı)

GDELT (Global Database of Events, Language, and Tone) dünya çapındaki haberleri sürekli olarak analiz eden bir veritabanıdır. Telif hakları nedeniyle haberlerin tam metnini vermez, ancak haberlere dair çok değerli meta veriler ve analitik skorlar sunar:

* **Haber Linki (URL):** Olayın geçtiği asıl kaynağa referans.
* **Tonalite (Tone):** Haberin duygu durum skorudur. Haberin pozitif mi yoksa negatif mi (panik, kriz vb.) olduğunu gösterir. Bu skor, fiyat dalgalanmalarındaki "Piyasa Algısı"nı ölçmek için kullanılır.
* **Temalar (Themes):** Haberin içerdiği anahtar kelimeler ve kavramlar. 

### Çekilen Kategoriler (Temalar) ve Nedenleri

Projemiz gıda tedarik zinciri şeffaflığı ve enflasyon şoklarını analiz ettiği için, küresel haber havuzundan sadece projemizi ilgilendiren aşağıdaki spesifik temalar ve ülkeler çekilmektedir:

**1. Gıda ve Tarım Şokları (Gıda Arzı):**
* `FOOD_SECURITY`, `AGRICULTURE`, `TAX_FOODSTAPLES_WHEAT`, `TAX_FOODSTAPLES_MEAT`, `WB_175_FERTILIZERS`
* *Neden?* Ürün rekoltesi, tarımsal krizler, et ve buğday gibi temel gıda fiyatlarındaki değişimler ile tarımsal girdi (gübre) maliyetlerini takip etmek için.

**2. Makroekonomi ve Enflasyon:**
* `ECON_INFLATION`, `ECON_COSTOFLIFE`, `ECON_PRICECONTROLS`, `TAX_ECON_PRICE`, `ECON_CURRENCY_EXCHANGE_RATE`, `ECON_INTEREST_RATES`
* *Neden?* Döviz, faiz ve genel enflasyon oranlarındaki değişimlerin gıda fiyatlarına yansımasını (gecikmeli etkisini) modelleyebilmek için.

**3. Enerji ve Lojistik Maliyetleri:**
* `FUELPRICES`, `ECON_OILPRICE`, `ENV_NATURALGAS`, `ECON_DIESELPRICE`, `WB_135_TRANSPORT`, `SUPPLY_CHAIN`
* *Neden?* Tarladan markete gelen ürünün arasındaki devasa fiyat marjının (uçurumunun) en büyük nedeni mazot ve taşıma maliyetleridir. Lojistik ve enerji fiyatlarındaki küresel şokları izlemek için.

**4. İklim ve Doğa Olayları:**
* `ENV_DROUGHT`, `NATURAL_DISASTER_FLOODS`, `ENV_CLIMATECHANGE`, `NATURAL_DISASTER_EXTREME_WEATHER`
* *Neden?* Kuraklık, don veya sel gibi bölgesel hava şoklarının sera ve tarlalara olan hasarının ürün fiyatını nasıl ve ne kadar sürede artırdığını analiz etmek için.

**5. İşgücü, Krizler ve Jeopolitik:**
* `UNEMPLOYMENT`, `WB_2670_JOBS`, `TAX_DISEASE_OUTBREAK`, `SMUGGLING`, `CORRUPTION`, `BLOCKADE`, `SANCTIONS`
* *Neden?* Tarım işçisi sorunları, salgın hastalıklar (şap, kuş gribi), gıda stokçuluğu (karaborsa) ve sınır kapılarının kapanması / ambargolar gibi tedarik zincirini aniden koparacak olayları tespit etmek için.

**İzlenen Ülkeler:**
* `Türkiye (TU)`, `Rusya (RS)`, `Ukrayna (UP)`, `Almanya (GM)`, `Irak (IZ)`, `Suriye (SY)`, `İran (IR)`, `Brezilya (BR)`, `Arjantin (AR)`, `Hollanda (NL)`, `İspanya (SP)`, `Mısır (EG)`
* *Neden?* Sadece Türkiye değil, Türkiye'nin gıda, canlı hayvan, tohum ve enerji ithalatı/ihracatı yaptığı ana stratejik partnerleri de izleyerek dışarıdan gelen şokların (Imported Inflation) etkisini tespit edebilmek için.
