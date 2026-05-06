# markettamam.com — Scrape Araştırması

Tarih: 2026-05-06
Hedef: `https://www.markettamam.com/` — Türkiye için market fiyatı toplayıcı.

## Site profili

- SvelteKit SSR uygulaması (server: nginx/1.24, response: x-sveltekit-page=true).
- CDN: `ixltj3ma.markettamam.com` (görseller, kategoriler, broşür PDF/webp).
- Anasayfa metadata: **293 depot, 972 nearestDepot, 2.907 broşür/aktüel, 11 ana kategori**.
- Kapsanan zincirler: Migros, Şok, BİM, A101, CarrefourSA, **Tarım Kredi, Metro** (marketfiyati'da olmayanlar var).
- Bonus özellikler: aktüel/broşür arşivi, karekod sorgulama, "en yakın market" listesi.

## Auth

- Anasayfaya bir GET atılınca site otomatik olarak `auth_token` cookie'si basıyor:
  - JWT payload: `email=demo@markettamam.com`, `nameid=3`, geçerli ~14 gün (`Max-Age=43200` her cookie hit'inde, `exp` ~14 gün).
  - `HttpOnly; Secure; SameSite=Lax`.
- Login yok. Demo erişim default. Production scraper için cookie'yi her oturumda anasayfa GET'i ile yenilemek yeterli.

## Veri formatı: SvelteKit `devalue`

Tüm route loader verisi `__data.json` ile sunuluyor — HTML parse gerekmiyor.

```
GET /{path}/__data.json
```

Yapı:

```jsonc
{
  "type": "data",
  "nodes": [
    { "type": "data", "data": [ /* layout flat array */ ] },
    { "type": "data", "data": [ /* page flat array */ ] }
  ]
}
```

Her `data` flat bir array. `data[0]` kök objedir; içindeki int değerler **aynı array'e index referansıdır** (devalue serialization). Cycle olmadan resolve edilebilir.

Minimal decoder (Python):

```python
def resolve(idx, flat, seen=None):
    seen = seen or set()
    if not isinstance(idx, int) or idx in seen:
        return idx
    seen = seen | {idx}
    v = flat[idx]
    if isinstance(v, dict):
        return {k: resolve(vv, flat, seen) for k, vv in v.items()}
    if isinstance(v, list):
        return [resolve(x, flat, seen) for x in v]
    return v

root = resolve(0, data["nodes"][1]["data"])
```

## Endpoint #1 — Kategori sayfası

```
GET /{slug}-pno-{N}-c-{base64-cat-id}/__data.json
```

- `slug`: SEO slug (kategorinin Türkçe adından, örn. `meyve`, `salca`, `kirmizi_et`).
- `N`: sayfa numarası (1'den başlar).
- `base64-cat-id`: `MTE1LWN0c2s` → decode `115-ctsk`. Yani **cat ID + sabit suffix** base64 url-safe.

Test: `/meyve-pno-1-c-MTE1LWN0c2s/__data.json` → 563 KB JSON.

Dönen `data[0]` kökü:

| Alan | Açıklama |
|---|---|
| `products` | Bu sayfadaki ürünlerin array'i |
| `pageNo` | Şu anki sayfa |
| `total` | Kategorideki toplam ürün sayısı (örn. 104) |
| `searchSubCatId` | Kategori ID |
| `title` | Sayfa başlığı |

Örnek `products[0]`:

```json
{
  "id": 156513,
  "categoryId": 115,
  "name": "Yerli Yaban Mersini (Blueberry) 125 Gr",
  "photoLink": "https://ixltj3ma.markettamam.com/images/productImages/...jpg",
  "priceRange": "79,00 - 164,90",
  "unitPriceRange": "Adet Fiyatı: 79,00 - 164,90",
  "depotId": 3454,
  "depotLat": 41.063148, "depotLon": 28.99846,
  "depotName": "Istanbul Mecıdıyeköy 2 Süper",
  "commonCode": "156513",
  "priceDate": "0001-01-01T00:00:00"  // kategori sayfasında stale
}
```

**Önemli**: kategori sayfasında `price` boş (0), `priceRange` string formatta min-max ("79,00 - 164,90"). Tek depot fiyatı için ürün detayına gitmek gerekir.

## Endpoint #2 — Ürün detay (asıl değerli olan)

```
GET /en-ucuz-{slug}-p-{base64-product-id}/__data.json
```

- `slug`: ürün adından üretilmiş (örn. `flotty_organik_m_orta_boy_yumurta_10_adet`).
- `base64-product-id`: `NTI1ODEtY21keg` → decode `52581-cmdz`. Yani **product ID + sabit suffix** base64 url-safe. Slug yanlış olsa bile ID doğruysa çalışıyor olabilir (test edilmeli — muhtemelen redirect var).

Dönen `data[0]` kökü:

| Alan | Açıklama |
|---|---|
| `product` | Ana ürün (metadata) |
| `product.sameCommonCodeProducts` | **Bu ürünün satıldığı her depot için ayrı kayıt** |
| `slug`, `commonCode`, `lat`, `lon`, `title` | Sayfa metadata |

`sameCommonCodeProducts[i]` — **scrape'in altın kaynağı**:

```json
{
  "id": 52581,
  "bazaarId": 24,                       // chain ID (24=Migros, 28=başka)
  "depotId": 1212,
  "depotName": "Bomonti M Migros",
  "depotLat": 41.06034, "depotLon": 28.98418,
  "price": 149.95,                      // TEK fiyat — range değil
  "unitPrice": 15.00,                   // birim fiyat (adet/kg)
  "unitId": 3,
  "priceDate": "2026-03-30T06:55:58.79", // bu fiyatın belirlendiği tarih
  "prevPrice": 149.95,                  // bir önceki fiyat
  "prevPriceDate": "2025-09-04T06:57:19.22", // bir önceki fiyatın tarihi
  "prevDiscountedPrice": 0,
  "stockCount": 0,
  "unitQuantity": "10"
}
```

Test edilen ürün (Flotty Organik Yumurta) için 7 depot listelendi (Migros zinciri + bir başka chain).

## marketfiyati.org.tr ile karşılaştırma

| Özellik | markettamam | marketfiyati |
|---|---|---|
| Auth | Demo JWT (otomatik) | Yok |
| Endpoint formatı | SvelteKit `__data.json` (devalue decode) | REST JSON |
| Fiyat granülaritesi (kategori) | Min-max range string | Depot bazlı tek fiyat |
| Fiyat granülaritesi (ürün detay) | **Depot bazlı tek fiyat + birim fiyat** | — |
| **Bir önceki fiyat (prevPrice + prevPriceDate)** | **VAR — tek scrape'te delta gözlemi** | Yok |
| Depot konumu (lat/lon) | Var | Var |
| Sayfa boyutu | ~? (kategori 104 ürün, page=1 → ?) | API page_size=25 hard limit |
| Tarımkredi / Metro kapsama | Var | Yok |
| Aktüel/broşür arşivi | Var (2.907 adet) | Yok |
| Tarihsel veri | Yok (sadece anlık + bir önceki nokta) | Yok (anlık) |

## En kritik bulgular

1. **`prevPrice` + `prevPriceDate` alanları** — bu scraper günlük çalışmasa bile her üründe **bir delta gözlemi** geliyor. Asymetrik fiyat geçişi ("rockets and feathers") analizi için marketfiyati'den **anlamlı şekilde daha iyi**.
2. **Demo JWT otomatik** — auth setup'ı yok. Anasayfa GET'i ile cookie tazeleniyor.
3. **Devalue formatı** — flat array + index reference. Decode edilebilir (~10 satır Python).
4. **Tarım Kredi + Metro coverage** — marketfiyati'da olmayan zincirler.
5. **Aktüel broşürler** — bonus veri kaynağı (PDF/webp). İndirim/promosyon sinyali için OCR ile fiyat çıkarılabilir.

## Açık sorular / next steps (scraper yazmadan önce)

- [ ] **Ürün detay slug doğrulanmadan ID ile çalışıyor mu?** (Yanlış slug → 200 mü 404 mü 301 mi?)
- [ ] **Kategori sayfa boyutu** kaç? `total=104` ürün için kaç sayfa dönüyor — `pno-1` ile kaç ürün geliyor?
- [ ] **Tüm kategoriler** listesini çıkar (anasayfa `__data.json`'dan): 11 ana + alt kategoriler.
- [ ] **`bazaarId` → chain adı** mapping (24=Migros tespit edildi, 28=?). Anasayfa "nearby markets" verisinden çıkarılabilir.
- [ ] **`unitId` → birim** mapping (1=KG?, 3=Adet?). Standardizasyon UDF'i için lazım.
- [ ] **Rate limit davranışı** — kaç istek/saniye sonra 429/disconnect? Marketfiyati'da exponential backoff (10s/20s/40s) gerekiyordu.
- [ ] **Karekod (barcode) endpoint'i** var mı? Entity resolution için altın değerinde olur (hal ↔ market eşleme).
- [ ] **Aktüel/broşür endpoint formatı** — ileride OCR pipeline için.

## Önerilen scraper akışı (taslak)

```
1) GET /__data.json
   → kategori ağacı + bazaar/depot listesi (293 depot)

2) Her (alt) kategori için:
   GET /{slug}-pno-{N}-c-{cat64}/__data.json
   → tüm sayfalar (total alanı paginated)
   → product id'leri topla

3) Her product id için:
   GET /en-ucuz-{slug}-p-{pid64}/__data.json
   → sameCommonCodeProducts → her depot×ürün için bir satır

4) JSONL yaz:
   ingestion/markettamam/data/YYYY-MM-DD/{kategori}.jsonl
   schema: {product_id, name, common_code, category_id,
            depot_id, depot_name, lat, lon, bazaar_id,
            price, unit_price, unit_id, unit_quantity,
            price_date, prev_price, prev_price_date,
            stock_count, scraped_at}

5) state.json ile staleness takibi (kategori bazlı)
```

Modül iskeleti `ingestion/market/` ile paralel:
- `client.py` — devalue decoder + 2 endpoint (anasayfa, kategori, ürün detay)
- `config.py` — kategori slug→id, bazaarId→chain mapping
- `scraper.py` — orchestration, async/await + backoff
- `state.py` — `state.json` (per-kategori last-scraped timestamps)
