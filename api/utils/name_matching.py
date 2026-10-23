"""Name normalisation and matching for Laguna municipalities and barangays."""

import logging
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

log = logging.getLogger("pipelines")

# (clean municipality, clean barangay as written in the source) -> official clean barangay
BGY_OVERRIDES: dict[tuple[str, str], str] = {
    ("SANTA ROSA", "POOC"): "POOK",
}


class UnmatchedNamesError(ValueError):
    """Source names that could not be matched to an official pcode."""


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 text that was decoded as cp1252 (e.g. 'BiÃ±an' -> 'Biñan')."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_text(text) -> str:
    """Normalise a place name so differently written names compare equal."""
    if text is None or pd.isna(text):
        return ""
    text = fix_mojibake(str(text))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.upper()
    text = re.sub(r"\([^)]*\)", "", text)                   # (POB.), (CAPITAL), ...
    text = re.sub(r"\b(CITY OF|MUNICIPALITY OF)\b", "", text)
    text = re.sub(r"\bCITY\b", "", text)
    text = re.sub(r"\bSTA\b\.?", "SANTA", text)
    text = re.sub(r"\bSTO\b\.?", "SANTO", text)
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


# ---- municipalities ----------------------------------------------------------
def build_municipality_lookup(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    """{clean name: pcode} from (pcode, official name) pairs. Ambiguity is an error."""
    lookup: dict[str, str] = {}
    for pcode, name in pairs:
        key = clean_text(name)
        if key in lookup and lookup[key] != pcode:
            raise ValueError(f"Two municipalities normalise to '{key}': {lookup[key]}, {pcode}")
        lookup[key] = pcode
    return lookup


def load_overrides(path: Path) -> dict[str, str]:
    """Optional CSV (raw_name, pcode) for names the normaliser cannot resolve."""
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).dropna()
    return {clean_text(r): p.strip() for r, p in zip(df["raw_name"], df["pcode"])}


def match_municipalities(
    raw_names: Iterable[str],
    lookup: dict[str, str],
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return {raw name: pcode}. Raises UnmatchedNamesError if any name fails."""
    overrides = overrides or {}
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    for raw in sorted({str(n) for n in raw_names if not pd.isna(n)}):
        key = clean_text(raw)
        pcode = overrides.get(key) or lookup.get(key)
        if pcode:
            matched[raw] = pcode
        else:
            unmatched.append(raw)
    if unmatched:
        raise UnmatchedNamesError(
            f"{len(unmatched)} municipality name(s) could not be matched: {unmatched}. "
            "Add them to pipelines/crosswalk/municipality_overrides.csv (raw_name,pcode)."
        )
    return matched


# ---- barangays (best effort: not needed for municipality-level tables) -----------
def build_barangay_lookup(lookup_df: pd.DataFrame) -> dict[tuple[str, str], str]:
    """{(municipality_pcode, clean barangay): barangay_pcode}.

    Keys that map to more than one barangay are dropped (and logged) instead of
    silently keeping whichever came last.
    """
    keyed = lookup_df.assign(clean_bgy=lookup_df["barangay_name"].apply(clean_text))
    counts = keyed.groupby(["municipality_pcode", "clean_bgy"])["barangay_pcode"].nunique()
    ambiguous = set(counts[counts > 1].index)
    if ambiguous:
        log.warning("%d ambiguous barangay name(s) excluded from matching", len(ambiguous))
    return {
        (m, b): p
        for m, b, p in zip(keyed["municipality_pcode"], keyed["clean_bgy"], keyed["barangay_pcode"])
        if (m, b) not in ambiguous
    }


def resolve_barangay(
    mun_raw: str, mun_pcode: str, bgy_raw: str, lookup: dict[tuple[str, str], str]
) -> str | None:
    key = clean_text(bgy_raw)
    key = clean_text(BGY_OVERRIDES.get((clean_text(mun_raw), key), key))
    return lookup.get((mun_pcode, key))
