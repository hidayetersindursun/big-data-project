import json
import unicodedata
import csv

# Fonksiyon: Türkçe karakterleri normalize et
def normalize_turkish(text):
    """Türkçe karakterleri normalize et, boşlukları alt çizgiye çevir"""
    if not text:
        return ""
    # Küçük harfe çevir
    text = text.lower()
    # Unicode normalize et (NFD) ve ASCII uyumlu yap
    nfd = unicodedata.normalize('NFD', text)
    normalized = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    # Özel Türkçe karakterler
    tr_map = {
        'ç': 'c', 'ş': 's', 'ğ': 'g', 'ı': 'i',
        'ö': 'o', 'ü': 'u'
    }
    for old, new in tr_map.items():
        normalized = normalized.replace(old, new)
    # Boşlukları alt çizgiye çevir, sayı/harf dışı karakterleri kaldır
    normalized = ''.join(c if c.isalnum() else '_' for c in normalized)
    # Birden çok alt çizgiyi tek bir tane yap
    while '__' in normalized:
        normalized = normalized.replace('__', '_')
    return normalized.strip('_')

# JSON dosyasını oku
with open('processing/silver/lookups/_chunks/chunk_07.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# CSV satırlarını hazırla
rows = []
hal_count = 0

for hal_product, hal_data in data.items():
    hal_count += 1
    candidates = hal_data.get('candidates', [])

    if not candidates:
        # Aday yoksa, reject satırı yaz
        rows.append({
            'hal_product': hal_product,
            'market_product': '',
            'product_canonical': '',
            'confidence': 'reject',
            'unit_conversion_factor': '1.0',
            'reason': 'Aday yok'
        })
        continue

    # Her aday için bir satır yaz
    for candidate in candidates:
        market_product = candidate.get('market_product', '')

        # Confidence ve canonical belirle
        confidence = "weak"  # Default
        reason = ""

        # İşlenmiş ürün kontrolü — normalize öncesi orijinal metinde kontrol
        # Salça, turşu, konserve, reçel, ezmesi, kreması, marmelatı
        processed_keywords_raw = [
            'salça', 'salca',
            'turşu', 'tursu',
            'konserve',
            'reçel', 'recel',
            'ezmesi', 'ezme',
            'kreması', 'kremasi', 'kreme', 'krem',
            'marmelatı', 'marmelat',
            'kurutulmuş', 'kurutulmus'
        ]
        market_lower = market_product.lower()
        is_processed = any(kw in market_lower for kw in processed_keywords_raw)

        if is_processed:
            # Kurutulmuş ama ürün adında yoksa (kurutulmuş bamya gibi) weak
            if 'kurutulmus' in market_lower:
                confidence = 'weak'
                reason = 'Kurutulmuş varyanı'
            else:
                confidence = 'reject'
                reason = 'İşlenmiş ürün'
        else:
            # Dondurulmuş kontrol
            if 'dondurulmus' in market_lower or 'dondurulmuş' in market_lower:
                confidence = 'weak'
                reason = 'Dondurulmuş varyanı'
            else:
                # Tam eşleşme veya kg uyumlu
                hal_base = normalize_turkish(hal_product)
                market_base = normalize_turkish(market_product)

                # Basit heuristic: market adında hal adı base'i varsa exact
                if hal_base in market_base:
                    confidence = 'exact'
                    reason = 'Aynı ürün'
                else:
                    confidence = 'kg_equivalent'
                    reason = 'Aynı ürün farklı paket'

        # Product canonical belirle
        product_canonical = normalize_turkish(hal_product)

        rows.append({
            'hal_product': hal_product,
            'market_product': market_product,
            'product_canonical': product_canonical,
            'confidence': confidence,
            'unit_conversion_factor': '1.0',
            'reason': reason
        })

# CSV dosyasını yaz
output_path = 'processing/silver/lookups/_chunks/mapping_07.csv'
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'hal_product', 'market_product', 'product_canonical',
        'confidence', 'unit_conversion_factor', 'reason'
    ], quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(rows)

print(f"Hal ürünleri işlendi: {hal_count}")
print(f"CSV satırları yazıldı: {len(rows)}")
print(f"Çıktı: {output_path}")
