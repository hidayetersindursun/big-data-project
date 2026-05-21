#!/usr/bin/env python3
import json
import re
import csv

# Read chunk
with open(r'C:\Users\PC_4719\PROJELER\big-data\processing\silver\lookups\_chunks\chunk_06.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def to_canonical(text):
    """Normalize Turkish text to lowercase slug without Turkish chars"""
    if not text:
        return ''
    replacements = {
        'ç': 'c', 'Ç': 'c',
        'ş': 's', 'Ş': 's',
        'ı': 'i', 'I': 'i',
        'ğ': 'g', 'Ğ': 'g',
        'ö': 'o', 'Ö': 'o',
        'ü': 'u', 'Ü': 'u'
    }
    text = text.lower()
    for tr, en in replacements.items():
        text = text.replace(tr, en)
    # Replace spaces/non-alpha with underscore, then clean
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^a-z0-9_]', '', text)
    return text

# CSV output path
csv_path = r'C:\Users\PC_4719\PROJELER\big-data\processing\silver\lookups\_chunks\mapping_06.csv'
rows_list = []
hal_count = 0

for hal_product, hal_data in data.items():
    hal_count += 1
    candidates = hal_data.get('candidates', [])

    for candidate in candidates:
        market_product = candidate.get('market_product', '')
        market_category = candidate.get('market_category', '')

        confidence = 'reject'
        product_canonical = ''
        unit_conversion_factor = '1.0'
        reason = ''

        # Keywords for processed products
        processed_keywords = ['marmelat', 'recel', 'konserve', 'salca', 'kurutulmus', 'kuru ', 'pekmez']
        market_lower = market_product.lower()
        hal_lower = hal_product.lower()

        # Is it frozen?
        is_frozen = 'dondurulmus' in market_lower

        # Is it processed/preserved?
        is_processed = any(kw in market_lower for kw in processed_keywords)

        # Check market category for processed items
        if market_category in ['Bal ve Reçel', 'Helva Tahin ve Pekmez', 'Yoğurt', 'Çay ve Bitki Çayları']:
            confidence = 'reject'
            reason = 'Urunlendirilmis urun kategorisi'
        elif is_processed:
            confidence = 'reject'
            reason = 'Islenmus - taze hal ile eslesmiyor'
        elif is_frozen:
            # Frozen version of fresh product
            hal_canonical = to_canonical(hal_product)
            product_canonical = hal_canonical
            confidence = 'weak'
            reason = 'Dondurulmus varyete'
        else:
            # Fresh produce - try to match
            hal_canonical = to_canonical(hal_product)
            market_canonical = to_canonical(market_product)

            # Try exact match on canonical forms
            if hal_canonical == market_canonical:
                confidence = 'exact'
                product_canonical = hal_canonical
                reason = 'Tam eslesme'
            elif hal_canonical in market_canonical:
                # Substring match - likely variety/packaging difference
                confidence = 'kg_equivalent'
                product_canonical = hal_canonical
                reason = 'Ayni urun - farkli paket/varyete'
            else:
                # No clear match
                confidence = 'reject'
                reason = 'Eslesmiyor'

        # Clean reason - no commas for CSV
        reason = reason.replace(',', '-')

        rows_list.append({
            'hal_product': hal_product,
            'market_product': market_product,
            'product_canonical': product_canonical,
            'confidence': confidence,
            'unit_conversion_factor': unit_conversion_factor,
            'reason': reason
        })

# Write CSV with proper quoting - use utf-8-sig for BOM
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    # Write header
    writer.writerow(['hal_product', 'market_product', 'product_canonical', 'confidence', 'unit_conversion_factor', 'reason'])
    # Write data rows
    for row in rows_list:
        writer.writerow([
            row['hal_product'],
            row['market_product'],
            row['product_canonical'],
            row['confidence'],
            row['unit_conversion_factor'],
            row['reason']
        ])

print(f'Processed {hal_count} hal products, wrote {len(rows_list)} CSV rows to {csv_path}')
