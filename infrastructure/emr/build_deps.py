#!/usr/bin/env python3
"""
EMR deps.zip olusturucu.

EMR cluster deploy-mode'da spark-submit yalnizca tek .py dosyasini indirir;
`utils/` paketi inmez. Bu script `processing/silver/utils/` klasorunu
`deps.zip`'e paketler (zip-kok adi `utils/`), boylece `--py-files deps.zip`
ile cluster'da `from utils.spark_session import ...` cozulur.

`zip` komutu gerektirmez — saf Python `zipfile`; Windows / EC2 / Git Bash'te calisir.

Cikti  : infrastructure/emr/deps.zip   (launch_demo.sh bunu S3'e yukler)
Kullanim: python build_deps.py
"""

import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
UTILS_DIR = _REPO / "processing" / "silver" / "utils"
OUTPUT = _HERE / "deps.zip"

# deps.zip icinde mutlaka bulunmasi gereken dosyalar (preflight de dogrular).
REQUIRED = ["__init__.py", "spark_session.py", "cities.py", "units.py", "partitions.py"]


def build():
    """deps.zip'i olusturur. Basari -> 0, hata -> 1 doner."""
    if not UTILS_DIR.is_dir():
        print(f"[build_deps] HATA: utils klasoru yok: {UTILS_DIR}", file=sys.stderr)
        return 1

    py_files = sorted(UTILS_DIR.glob("*.py"))
    names = {p.name for p in py_files}
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        print(f"[build_deps] HATA: utils/ icinde eksik dosya(lar): {missing}",
              file=sys.stderr)
        return 1

    if OUTPUT.exists():
        OUTPUT.unlink()

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in py_files:
            zf.write(p, f"utils/{p.name}")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"[build_deps] OK: {OUTPUT.name} ({size_kb:.1f} KB, "
          f"{len(py_files)} dosya: {sorted(names)})")
    return 0


if __name__ == "__main__":
    sys.exit(build())
