# Docker Kurulum Planı

## Servisler

| Servis | Port | Açıklama |
|---|---|---|
| Zookeeper | 2181 | Kafka'nın bağımlılığı |
| Kafka | 9092 | Mesaj kuyruğu |
| Apache NiFi | 8080 | Veri pipeline (scraper → Kafka) |
| MinIO | 9000 / 9001 | S3 yerel alternatif (Bronze/Silver/Gold) |

---

## TODO Listesi

### 1. Hazırlık
- [ ] Docker Desktop kurulu mu kontrol et (`docker --version`)
- [ ] Proje klasöründe `infrastructure/` klasörü aç
- [ ] `infrastructure/docker-compose.yml` dosyasını oluştur

### 2. docker-compose.yml Yazımı
- [ ] Zookeeper servisi ekle
- [ ] Kafka servisi ekle (Zookeeper'a bağlı)
- [ ] NiFi servisi ekle
- [ ] MinIO servisi ekle
- [ ] Tüm servisler aynı Docker network'ünde mi kontrol et

### 3. Kafka Topic'leri Oluştur
- [ ] `raw_market_prices`
- [ ] `raw_hal_prices`
- [ ] `raw_weather`
- [ ] `raw_gdelt`
- [ ] `raw_epias`
- [ ] `raw_tcmb`

### 4. NiFi Pipeline Kurulumu
- [ ] NiFi arayüzüne gir: http://localhost:8080/nifi
- [ ] `GetFile` processor ekle → `ingestion/data/` klasörünü izlesin
- [ ] `SplitText` processor ekle → her satırı (ürün) ayırsın
- [ ] `PublishKafka` processor ekle → `raw_market_prices` topic'ine göndersin
- [ ] Hal verisi için aynı pipeline'ı kur → `raw_hal_prices` topic'i

### 5. MinIO Kurulumu
- [ ] MinIO arayüzüne gir: http://localhost:9001
- [ ] `bronze` bucket oluştur
- [ ] `silver` bucket oluştur
- [ ] `gold` bucket oluştur
- [ ] Access key / Secret key not al → scraper'da kullanılacak

### 6. Test
- [ ] `docker-compose up -d` çalışıyor mu?
- [ ] `docker ps` ile tüm containerlar ayakta mı?
- [ ] Kafka'ya test mesajı gönder, geldi mi kontrol et
- [ ] scraper.py çalıştır → NiFi alıyor mu → Kafka'ya gidiyor mu?

### 7. EC2'ye Taşıma (Sonraki Adım)
- [ ] EC2 instance aç (t3.xlarge — min 16GB RAM)
- [ ] EC2'ye Docker + Docker Compose kur
- [ ] `docker-compose.yml` dosyasını EC2'ye kopyala (`scp`)
- [ ] EC2'de `docker-compose up -d`
- [ ] Security group'ta portları aç (8080, 9092, 9000, 9001)
- [ ] İleride MinIO → AWS S3'e geçişte sadece endpoint URL değiştir

---

## Notlar

- Lokal geliştirme için MinIO kullan, AWS S3'e geçmek istersen `boto3` endpoint'ini değiştirmen yeterli
- NiFi ilk açılışta yavaş başlar (~2-3 dk bekle)
- Kafka için Zookeeper şart, önce Zookeeper ayağa kalkar
- EC2'de t2.micro/nano ile bu stack açılmaz, en az **t3.xlarge** kullan
