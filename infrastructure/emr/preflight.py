#!/usr/bin/env python3
"""
EMR pre-flight -- cluster ACMADAN tum dagitim hatalarini yakalar.

EMR'da aldigimiz hatalarin hicbiri Spark mantiginda degildi; hepsi dagitim
katmanindaydi (paketleme, S3 yollari, step arg formati). Bu script o katmani
cluster gerektirmeden dogrular. Herhangi bir FAIL'de exit!=0 doner; launch_demo.sh
bunu gorunce cluster acmadan durur -- yani "ac-gor-kapat-duzelt" dongusu biter.

Kontroller:
  1. py_compile  -- 9 step script + utils/*.py sozdizimi
  2. deps.zip    -- taze kurulum + utils/ paketi icerigi
  3. steps.json  -- gecerli JSON; Type=Spark; literal spark-submit YOK; --py-files var
  4. S3          -- girdi tablolari + yuklenen kod (deps.zip, scriptler, lookup csv)

Kullanim:
  python preflight.py            # tam: yerel + S3 (aws s3 sync sonrasi calistir)
  python preflight.py --no-s3    # yalnizca yerel kontroller (cluster/aws gerekmez)
"""

import argparse
import json
import py_compile
import subprocess
import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
import build_deps  # noqa: E402

STEPS_JSON = _HERE / "steps.json"
DEPS_ZIP = _HERE / "deps.zip"

# Pipeline'in okudugu, hicbir EMR step'inin URETMEDIGI S3 girdi tablolari.
# ZORUNLU: silver_joined (trunk -- her Gold tablo bunun ustunde) + gdelt_silver girdileri.
S3_INPUTS_REQUIRED = [
    "silver/market_prices",
    "silver/hal_prices",
    "bronze/gdelt",
]
# OPSIYONEL: tek bir Gold analizini besler; yoksa o step bos kalir ama
# ActionOnFailure=CONTINUE sayesinde pipeline devam eder.
S3_INPUTS_WARN = [
    "silver/weather_daily",         # shock_propagation
    "silver/akaryakit",             # macro_price_corr
    "silver/tcmb",                  # macro_price_corr
    "silver/commodities",           # macro_price_corr
    "silver/epias/price_and_cost",  # macro_price_corr
]

_results = []  # (level, ok, label, detail)


def check(ok, label, detail="", warn_only=False):
    level = "WARN" if warn_only else "FAIL"
    _results.append((level, bool(ok), label, detail))
    tag = "PASS" if ok else level
    line = f"  [{tag}] {label}"
    if detail:
        line += f"  --  {detail}"
    print(line)
    return bool(ok)


def s3_exists(uri):
    """aws s3 ls <uri> -- exit 0 ve cikti dolu ise True; aws CLI yoksa None."""
    try:
        r = subprocess.run(["aws", "s3", "ls", uri],
                           capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def check_steps_json():
    print("\n-- steps.json denetimi --")
    if not STEPS_JSON.is_file():
        check(False, "steps.json mevcut", str(STEPS_JSON))
        return None
    try:
        steps = json.loads(STEPS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        check(False, "steps.json gecerli JSON", str(e))
        return None
    if not (isinstance(steps, list) and steps):
        check(False, "steps.json bos olmayan liste")
        return None
    check(True, "steps.json gecerli JSON", f"{len(steps)} step")

    for st in steps:
        name = st.get("Name", "?")
        args = st.get("Args", []) or []
        check(st.get("Type") == "Spark", f"[{name}] Type=Spark", str(st.get("Type")))
        # EMR Type:Spark spark-submit'i kendi ekler -- Args'ta literal olmamali
        check("spark-submit" not in args,
              f"[{name}] Args'ta literal spark-submit yok")
        check("--py-files" in args, f"[{name}] --py-files var")
        py = [a for a in args
              if isinstance(a, str) and a.startswith("s3://") and a.endswith(".py")]
        check(len(py) == 1, f"[{name}] tam 1 adet .py script yolu", str(py))
        aof = st.get("ActionOnFailure")
        check(aof in ("TERMINATE_CLUSTER", "CONTINUE", "CANCEL_AND_WAIT"),
              f"[{name}] ActionOnFailure gecerli", str(aof))
    return steps


def check_compile(rel_paths):
    print("\n-- Python derleme (py_compile) --")
    for rel in rel_paths:
        local = _REPO / rel
        if not local.is_file():
            check(False, f"derle {rel}", "yerel dosya yok")
            continue
        try:
            py_compile.compile(str(local), doraise=True)
            check(True, f"derle {rel}")
        except py_compile.PyCompileError as e:
            msg = str(e).strip().splitlines()[-1][:140]
            check(False, f"derle {rel}", msg)


def check_deps_zip():
    print("\n-- deps.zip (taze kurulum + icerik) --")
    rc = build_deps.build()
    if rc != 0 or not DEPS_ZIP.is_file():
        check(False, "deps.zip olusturuldu")
        return
    check(True, "deps.zip olusturuldu", DEPS_ZIP.name)
    try:
        with zipfile.ZipFile(DEPS_ZIP) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        check(False, "deps.zip gecerli zip dosyasi")
        return
    want = {f"utils/{n}" for n in build_deps.REQUIRED}
    miss = want - names
    check(not miss, "deps.zip icerigi (utils/ paketi)",
          f"eksik: {sorted(miss)}" if miss else f"{sorted(names)}")


def check_s3(steps, bucket):
    print("\n-- S3 kontrolleri --")
    base = f"s3://{bucket}"
    probe = s3_exists(base + "/")
    if probe is None:
        check(False, "aws CLI kullanilabilir",
              "aws komutu PATH'te yok -- S3 kontrolleri yapilamadi")
        return
    check(bool(probe), f"S3 bucket erisilebilir ({bucket})")

    for prefix in S3_INPUTS_REQUIRED:
        ok = s3_exists(f"{base}/{prefix}/")
        check(bool(ok), f"girdi (zorunlu): {prefix}",
              "" if ok else "S3'te bulunamadi")
    for prefix in S3_INPUTS_WARN:
        ok = s3_exists(f"{base}/{prefix}/")
        check(bool(ok), f"girdi (opsiyonel): {prefix}",
              "" if ok else "yok -- ilgili Gold step ciktisi bos kalir",
              warn_only=True)

    seen = set()
    for st in steps:
        for a in st.get("Args", []) or []:
            if (isinstance(a, str) and a.startswith("s3://")
                    and a.endswith(".py") and a not in seen):
                seen.add(a)
                ok = s3_exists(a)
                short = a.split("/code/", 1)[-1]
                check(bool(ok), f"yuklu script: {short}",
                      "" if ok else "S3'te yok -- 'aws s3 sync' calisti mi?")

    for uri, label in [
        (f"{base}/code/deps.zip", "yuklu: code/deps.zip"),
        (f"{base}/bootstrap/install_libs.sh", "yuklu: bootstrap/install_libs.sh"),
        (f"{base}/code/processing/silver/lookups/hal_market_mapping.csv",
         "yuklu: lookups/hal_market_mapping.csv"),
    ]:
        ok = s3_exists(uri)
        check(bool(ok), label, "" if ok else "S3'te yok")


def main():
    ap = argparse.ArgumentParser(description="EMR pre-flight dogrulama")
    ap.add_argument("--no-s3", action="store_true",
                    help="S3 kontrollerini atla (yalnizca yerel: derleme + deps.zip + steps.json)")
    args = ap.parse_args()

    print("=" * 64)
    print("EMR PRE-FLIGHT  --  cluster ACMADAN dogrulama")
    print("=" * 64)

    steps = check_steps_json()
    if steps is None:
        print("\nSONUC: FAIL -- steps.json okunamadi, devam edilemiyor.")
        return 1

    bucket = None
    script_s3 = []
    for st in steps:
        for a in st.get("Args", []) or []:
            if isinstance(a, str) and a.startswith("s3://") and a.endswith(".py"):
                if bucket is None:
                    bucket = a.split("/")[2]
                if a not in script_s3:
                    script_s3.append(a)
    local_scripts = []
    for a in script_s3:
        if "/code/" in a:
            rel = a.split("/code/", 1)[-1]
            if rel not in local_scripts:
                local_scripts.append(rel)
    utils_rel = [f"processing/silver/utils/{n}" for n in build_deps.REQUIRED]

    check_compile(local_scripts + utils_rel)
    check_deps_zip()
    if args.no_s3:
        print("\n-- S3 kontrolleri ATLANDI (--no-s3) --")
    else:
        check_s3(steps, bucket or "s3-bbuckett")

    fails = [r for r in _results if (not r[1]) and r[0] == "FAIL"]
    warns = [r for r in _results if (not r[1]) and r[0] == "WARN"]
    passed = sum(1 for r in _results if r[1])
    print("\n" + "=" * 64)
    print(f"Ozet: {passed}/{len(_results)} PASS, {len(fails)} FAIL, {len(warns)} WARN")
    for _, _, label, detail in warns:
        print(f"  WARN: {label}" + (f"  --  {detail}" if detail else ""))
    if fails:
        print("\nSONUC: FAIL -- su sorunlar duzeltilmeden EMR ACILMAMALI:")
        for _, _, label, detail in fails:
            print(f"  - {label}" + (f"  ({detail})" if detail else ""))
        return 1
    print("\nSONUC: PASS -- EMR launch icin hazir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
