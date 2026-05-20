"""
Claude Haiku ile entity resolution: hal urun ↔ market title eşleştirmesi.

Girdi:  lookups/hal_market_candidates.json  (build_mapping_skeleton.py çıktısı)
Çıktı:  lookups/hal_market_mapping_draft.csv

Akış:
  - Her batch'te BATCH_SIZE hal ürünü + adayları tek prompt'ta gönder.
  - System prompt prompt-cache ile statik tutulur (TR ürün eşleştirme talimatı).
  - Response: JSON array, her hal ürünü için match listesi.
  - Tüm batch sonuçları CSV'ye yazılır.

Sonra manuel review:
  1. Excel'de hal_market_mapping_draft.csv'yi aç.
  2. confidence 'exact' veya 'kg_equivalent' olanları gözden geçir.
  3. Yanlışları 'reject' yap, kaçırılanları ekle.
  4. Filtrelenmiş halini hal_market_mapping.csv olarak kaydet (git'e commit edilir).

Kullanım:
  export ANTHROPIC_API_KEY=sk-ant-...
  python processing/silver/build_mapping_with_claude.py
  python processing/silver/build_mapping_with_claude.py --batch-size 5 --limit 100 --dry-run
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable

# Anthropic SDK
try:
    from anthropic import Anthropic
except ImportError:
    print("HATA: anthropic kütüphanesi yok. 'pip install anthropic' çalıştırın.", file=sys.stderr)
    sys.exit(1)

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

LOOKUP_DIR = Path(__file__).resolve().parent / "lookups"
IN_FILE = LOOKUP_DIR / "hal_market_candidates.json"
OUT_FILE = LOOKUP_DIR / "hal_market_mapping_draft.csv"
PROGRESS_FILE = LOOKUP_DIR / ".mapping_progress.json"

MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 8  # 8 hal ürünü tek API çağrısında
MAX_RETRIES = 3

SYSTEM_PROMPT = """Sen bir Türkiye gıda ürün eşleştirme uzmanısın. Hal (toptan) ürün isimleri ile
market raf ürün isimlerini eşleştiriyorsun.

Görev: Sana bir hal ürünü adı (örn. "DOMATES SOFRALIK") ve birkaç market ürünü adayı verilecek
(örn. "Domates Sofralık 1 Kg", "Salkım Domates 500 Gr"). Her aday için aşağıdaki kararı veriyorsun:

confidence değerleri:
  - "exact"          → aynı ürün, aynı varyete; doğrudan kg karşılaştırılabilir
  - "kg_equivalent"  → aynı ürünün farklı paketi/varyantı, kg cinsinden kıyaslanabilir
  - "weak"           → aynı kategori ama farklı ürün (örn. Domates Sofralık vs Domates Salkım)
  - "reject"         → eşleşmiyor

unit_conversion_factor: market_price'ı per-kg'a çevirmek için çarpan.
  - "1 Kg" ürün için: 1.0
  - "500 Gr" ürün için: 1.0 (unitPriceValue zaten /Kg)
  - "3 adet ≈ 600gr" gibi belirsiz: 1.0 (varsayılan)

product_canonical: tüm aynı ürünleri birleştirecek lowercase slug (örn. "domates_sofralik").

Cevabını SADECE şu JSON formatında ver (markdown code block kullanma, sadece raw JSON):
[
  {
    "hal_product": "DOMATES SOFRALIK",
    "matches": [
      {
        "market_product": "Domates Sofralık 1 Kg",
        "confidence": "exact",
        "unit_conversion_factor": 1.0,
        "product_canonical": "domates_sofralik",
        "reason": "Aynı ürün adı, kg cinsinden"
      },
      {
        "market_product": "Salkım Domates 500 Gr",
        "confidence": "weak",
        "unit_conversion_factor": 1.0,
        "product_canonical": "domates_salkim",
        "reason": "Farklı domates varyetesi"
      }
    ]
  }
]
"""


def build_user_message(batch: list) -> str:
    """Bir batch için user mesajını oluştur."""
    lines = []
    for item in batch:
        hal_name = item["hal_product"]
        cands = item["candidates"]
        lines.append(f"\n## Hal ürün: \"{hal_name}\"  (kategori: {item.get('hal_category')})")
        lines.append("### Adaylar:")
        for c in cands:
            lines.append(f"  - \"{c['market_product']}\"  (kategori: {c.get('market_category')})")
    lines.append("\nLütfen her hal ürünü için match listesini JSON formatında ver.")
    return "\n".join(lines)


def parse_response(text: str) -> list:
    """Modelin döndürdüğü JSON'u parse et. Markdown wrapping varsa temizle."""
    text = text.strip()
    if text.startswith("```"):
        # ```json ... ``` veya ``` ... ``` formatını temizle
        lines = text.split("\n")
        # İlk ve son satırları at
        text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
    return json.loads(text)


def call_claude(client, batch: list, dry_run: bool) -> list:
    """Bir batch için Haiku çağrısı yap, sonucu döndür."""
    if dry_run:
        # Dry run: ilk adayı 'exact' olarak işaretle
        return [{
            "hal_product": item["hal_product"],
            "matches": [{
                "market_product": item["candidates"][0]["market_product"] if item["candidates"] else "",
                "confidence": "exact",
                "unit_conversion_factor": 1.0,
                "product_canonical": item["hal_product"].lower().replace(" ", "_"),
                "reason": "DRY RUN",
            }] if item["candidates"] else []
        } for item in batch]

    user_msg = build_user_message(batch)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text
            return parse_response(text)
        except Exception as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{MAX_RETRIES}] {e} — {wait}s bekliyor", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Claude çağrısı {MAX_RETRIES} kez başarısız: {last_err}")


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return set(json.load(f).get("done", []))
    return set()


def save_progress(done: set):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(done)}, f, ensure_ascii=False)


def chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None,
                        help="İlk N hal ürünü ile sınırla (test için)")
    parser.add_argument("--dry-run", action="store_true",
                        help="API çağırma, sentetik cevap üret")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="progress dosyasından kaldığı yerden devam (default: true)")
    args = parser.parse_args()

    if not IN_FILE.exists():
        print(f"HATA: {IN_FILE} bulunamadı. Önce build_mapping_skeleton.py çalıştırın.",
              file=sys.stderr)
        sys.exit(1)

    with open(IN_FILE, encoding="utf-8") as f:
        candidates_data = json.load(f)

    items = [
        {"hal_product": name, **info}
        for name, info in candidates_data.items()
        if info["candidates"]  # adayı olmayanları atla
    ]
    if args.limit:
        items = items[: args.limit]

    done = load_progress() if args.resume else set()
    items_todo = [it for it in items if it["hal_product"] not in done]
    print(f"Toplam: {len(items)}  Atlanan (done): {len(items) - len(items_todo)}  "
          f"İşlenecek: {len(items_todo)}")

    if not args.dry_run:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("HATA: ANTHROPIC_API_KEY env değişkeni yok.", file=sys.stderr)
            sys.exit(1)
        client = Anthropic(api_key=api_key)
    else:
        client = None

    # CSV setup (append mode)
    write_header = not OUT_FILE.exists()
    csv_fp = open(OUT_FILE, "a", encoding="utf-8", newline="")
    writer = csv.DictWriter(csv_fp, fieldnames=[
        "hal_product", "market_product", "product_canonical",
        "confidence", "unit_conversion_factor", "reason",
    ])
    if write_header:
        writer.writeheader()

    total_batches = (len(items_todo) + args.batch_size - 1) // args.batch_size
    print(f"Batch sayısı: {total_batches}  (batch_size={args.batch_size})")
    start = time.time()

    try:
        for idx, batch in enumerate(chunks(items_todo, args.batch_size), 1):
            print(f"\n[{idx}/{total_batches}] {len(batch)} hal ürünü işleniyor...")
            results = call_claude(client, batch, args.dry_run)
            for r in results:
                hal_name = r.get("hal_product", "")
                for m in r.get("matches", []):
                    writer.writerow({
                        "hal_product": hal_name,
                        "market_product": m.get("market_product", ""),
                        "product_canonical": m.get("product_canonical", ""),
                        "confidence": m.get("confidence", "weak"),
                        "unit_conversion_factor": m.get("unit_conversion_factor", 1.0),
                        "reason": m.get("reason", ""),
                    })
                done.add(hal_name)
            csv_fp.flush()
            save_progress(done)

            elapsed = time.time() - start
            avg = elapsed / idx
            remaining = (total_batches - idx) * avg
            print(f"  Tamamlandı. Geçen: {elapsed:.1f}s  ETA: {remaining:.0f}s")
    finally:
        csv_fp.close()

    print(f"\nÇıktı: {OUT_FILE}")
    print(f"Sonraki adım: Excel'de aç, manuel review, hal_market_mapping.csv olarak kaydet.")


if __name__ == "__main__":
    main()
