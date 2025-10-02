#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule-based NLP extraction for colonoscopy reports
-------------------------------------------------
Extracts procedural variables from free-text reports using keyword/regex heuristics.

Variables:
- cecal_intubation: 1/0
- ileal_intubation: 1/0
- polyp_present: 1/0
- polyp_count: integer (best-effort)
- largest_polyp_size_mm: float (best-effort, takes the max numeric size in mm)
- largest_polyp_size_bucket: "<5 mm", "5–9 mm", "≥10 mm"
- polyp_locations: pipe-separated locations (cecum/right/transverse/left/sigmoid/rectum/ileum/multifocal/rectosigmoid)
- polypectomy_method: one of ["biopsy forceps","cold snare","hot snare","EMR","ESD","not removed","unknown"]
- post_polypectomy_bleeding: 0/1/2 -> 0=no, 1=suspected, 2=present
- hemoclip_applied: 1/0

Usage:
    python rule_based_extraction.py --input reports.xlsx --text-col BULGULAR --out extracted.csv

Notes:
- Patterns are bilingual (TR + EN) and robust to common spelling variants.
- This is a deterministic heuristic layer intended to complement supervised ML classification.
"""

import re
import argparse
from typing import List, Optional, Tuple, Dict
import pandas as pd

# -------------------- Normalization --------------------

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower()
    # Normalize common punctuation variants
    s = re.sub(r"\s+", " ", s)
    s = s.replace("ı", "i").replace("İ", "i")
    s = s.replace("ş", "s").replace("Ş", "s")
    s = s.replace("ğ", "g").replace("Ğ", "g")
    s = s.replace("ü", "u").replace("Ü", "u")
    s = s.replace("ö", "o").replace("Ö", "o")
    s = s.replace("ç", "c").replace("Ç", "c")
    return s.strip()

# -------------------- Cecal / Ileal intubation --------------------
CECAL_POS = [
    r"cekuma (ulasildi|ilerlenildi|gelindi|girildi)",
    r"cekuma kadar ilerlen",
    r"cecum (reached|intubated)",
    r"ti c|ti-c|ti-c?i? completed",  # common shorthand noise
    r"cecal intubation (achieved|successful)",
]
CECAL_NEG = [
    r"cekuma (ulasilamadi|gidilemedi|ilerlenemedi)",
    r"cec(um|al) (not reached|not intubated|could not be reached)",
]

ILEAL_POS = [
    r"terminal ileum (lumen|mukoza)?(si)? normal(di)?",
    r"ileuma (ulasildi|girildi|ilerlenildi)",
    r"ileal (intubation|exam(in(ed|ation))? completed)",
    r"ti (gorus|mukoza|lumen)",
]
ILEAL_NEG = [
    r"ileuma (ulasilamadi|girilemedi|ilerlenemedi)",
    r"ileal intubation (not achieved|failed|unsuccessful)",
]

def any_match(patterns: List[str], txt: str) -> bool:
    return any(re.search(p, txt) for p in patterns)

def extract_cecal_ileal(txt: str) -> Tuple[Optional[int], Optional[int]]:
    t = normalize_text(txt)
    cecal = None
    ileal = None
    if any_match(CECAL_POS, t):
        cecal = 1
    if any_match(CECAL_NEG, t):
        cecal = 0
    if any_match(ILEAL_POS, t):
        ileal = 1
    if any_match(ILEAL_NEG, t):
        ileal = 0
    return cecal, ileal

# -------------------- Polyp presence / count / size --------------------

POLYP_POS = [
    r"\bpolip\b",
    r"polipo?id",
    r"adenom",
    r"lesyon (goruldu|mevcut|izlendi|saptandi)",
    r"polyp|adenoma",
]
POLYP_NEG_HINTS = [
    r"polip (gorulmedi|saptanmadi|izlenmedi|yok)",
    r"no (polyp|adenoma)",
]

SIZE_PAT = r"(?:(\d+(?:\.\d+)?)\s*[-xX×]?\s*(\d+(?:\.\d+)?)?\s*mm)"
# captures 10 mm OR 10x8 mm etc.

def extract_polyp_presence(txt: str) -> int:
    t = normalize_text(txt)
    if any_match(POLYP_NEG_HINTS, t):
        return 0
    return 1 if any_match(POLYP_POS, t) else 0

def extract_polyp_count(txt: str) -> Optional[int]:
    t = normalize_text(txt)
    # explicit count patterns
    # e.g., "3 adet polip", "iki polip", "multiple polyps"
    DIGIT_PAT = r"(\d+)\s*(adet)?\s*polip"
    WORDNUM = {
        "bir":1,"iki":2,"uc":3,"dort":4,"bes":5,"alti":6,"yedi":7,"sekiz":8,"dokuz":9,
        "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
        "multiple":3,"coklu":3
    }
    m = re.search(DIGIT_PAT, t)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    for w, v in WORDNUM.items():
        if re.search(rf"\b{w}\b\s*(adet)?\s*polip", t):
            return v
    # fallback: if mentions polyp but no count, return 1
    return 1 if extract_polyp_presence(t) == 1 else None

def extract_size_info(txt: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Finds the largest mm value mentioned and returns bucket.
    """
    t = normalize_text(txt)
    sizes = []
    for m in re.finditer(SIZE_PAT, t):
        a = m.group(1)
        b = m.group(2)
        nums = []
        if a:
            try: nums.append(float(a))
            except: pass
        if b:
            try: nums.append(float(b))
            except: pass
        if nums:
            sizes.append(max(nums))
    if not sizes:
        return None, None
    mx = max(sizes)
    if mx < 5:
        bucket = "<5 mm"
    elif mx < 10:
        bucket = "5–9 mm"
    else:
        bucket = "≥10 mm"
    return mx, bucket

# -------------------- Locations --------------------

LOC_PATTERNS: Dict[str, List[str]] = {
    "cecum": [r"cek(um|um)?\b", r"\bcecum\b"],
    "right": [r"\bsag\b", r"\bright (colon)?\b"],
    "transverse": [r"\btransvers\b", r"\btransverse\b"],
    "left": [r"\bsol\b", r"\bleft (colon)?\b"],
    "sigmoid": [r"\bsigmoid\b"],
    "rectum": [r"\brektum\b", r"\brectum\b"],
    "rectosigmoid": [r"rektosigmoid", r"rectosigmoid"],
    "ileum": [r"\bileum\b", r"\bileum?\b"],
    "multifocal": [r"multifokal|multiple sites|diffuse"],
}

def extract_locations(txt: str) -> str:
    t = normalize_text(txt)
    hits = []
    for loc, pats in LOC_PATTERNS.items():
        if any(re.search(p, t) for p in pats):
            hits.append(loc)
    # de-duplicate and stable order
    order = ["cecum","right","transverse","left","sigmoid","rectum","rectosigmoid","ileum","multifocal"]
    hits_sorted = [h for h in order if h in hits]
    return "|".join(hits_sorted) if hits_sorted else ""

# -------------------- Polypectomy method --------------------

POLYPECTOMY_MAP = {
    "biopsy forceps": [r"biyopsi pensi", r"biopsy forceps"],
    "cold snare": [r"soguk snare", r"cold snare"],
    "hot snare": [r"sicak snare", r"hot snare"],
    "EMR": [r"\bemr\b", r"mukozal rezeksiyon"],
    "ESD": [r"\besd\b", r"submukozal diseksiyon"],
    "not removed": [r"cikartilmadi|eksizyon yapilmadi|remove edilmedi|not removed"],
}

def extract_polypectomy_method(txt: str) -> str:
    t = normalize_text(txt)
    for k, pats in POLYPECTOMY_MAP.items():
        if any(re.search(p, t) for p in pats):
            return k
    # infer from cautery/clip context if possible
    if re.search(r"snare", t):
        # default to unspecified snare -> cold snare if 'cold' present else hot if 'cautery' present
        if "cold" in t or "soguk" in t:
            return "cold snare"
        if "hot" in t or "sicak" in t or "cauter" in t:
            return "hot snare"
        return "unknown"
    if "forceps" in t or "pensi" in t:
        return "biopsy forceps"
    return "unknown"

# -------------------- Bleeding / Hemoclip --------------------

def extract_bleeding(txt: str) -> Optional[int]:
    """
    0=no, 1=suspected, 2=present
    """
    t = normalize_text(txt)
    if re.search(r"kanama (yok|izlenmedi|saptanmadi)|no bleeding", t):
        return 0
    if re.search(r"(aktif )?kanama (mevcut|izlendi|saptandi)|active bleeding|spurting|oozing", t):
        return 2
    if re.search(r"kanama supheli|suspected bleeding", t):
        return 1
    return None

def extract_hemoclip(txt: str) -> Optional[int]:
    t = normalize_text(txt)
    if re.search(r"hemoklip|hemoclip|clip uygul", t):
        return 1
    if re.search(r"klip uygulanmadi|no clip", t):
        return 0
    return None

# -------------------- Main apply --------------------

def apply_rules_to_series(s: pd.Series) -> pd.DataFrame:
    out = dict(
        cecal_intubation=[],
        ileal_intubation=[],
        polyp_present=[],
        polyp_count=[],
        largest_polyp_size_mm=[],
        largest_polyp_size_bucket=[],
        polyp_locations=[],
        polypectomy_method=[],
        post_polypectomy_bleeding=[],
        hemoclip_applied=[],
    )
    for txt in s.fillna("").astype(str).tolist():
        cecal, ileal = extract_cecal_ileal(txt)
        out["cecal_intubation"].append(cecal)
        out["ileal_intubation"].append(ileal)
        out["polyp_present"].append(extract_polyp_presence(txt))
        out["polyp_count"].append(extract_polyp_count(txt))
        size_mm, bucket = extract_size_info(txt)
        out["largest_polyp_size_mm"].append(size_mm)
        out["largest_polyp_size_bucket"].append(bucket)
        out["polyp_locations"].append(extract_locations(txt))
        out["polypectomy_method"].append(extract_polypectomy_method(txt))
        out["post_polypectomy_bleeding"].append(extract_bleeding(txt))
        out["hemoclip_applied"].append(extract_hemoclip(txt))
    return pd.DataFrame(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to .xlsx or .csv file containing reports")
    ap.add_argument("--text-col", default="BULGULAR", help="Name of the text column with colonoscopy findings")
    ap.add_argument("--out", required=True, help="Path to output .csv")
    args = ap.parse_args()

    # Load
    if args.input.lower().endswith(".xlsx"):
        df = pd.read_excel(args.input)
    else:
        df = pd.read_csv(args.input)

    if args.text_col not in df.columns:
        raise SystemExit(f"Text column '{args.text_col}' not found. Available: {list(df.columns)}")

    features = apply_rules_to_series(df[args.text_col])
    out_df = pd.concat([df, features], axis=1)
    out_df.to_csv(args.out, index=False)
    print(f"Saved extracted features to: {args.out}")
    # quick prevalence print
    print(out_df[["cecal_intubation","ileal_intubation","polyp_present"]].describe(include='all'))

if __name__ == "__main__":
    main()
