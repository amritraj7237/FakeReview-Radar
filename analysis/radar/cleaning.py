"""Load review data and clean it with a cleaning log (PRD section 8, docs/CLEANING_RULES.md).

Two principles:
    1. Never silently delete. Only exact duplicates (R3) are removed; every other
       problem keeps the row and only takes it out of the calculations it would spoil.
    2. Never invent values. Missing stays missing (NA / "unknown").

Every rule writes one row to the log on every run, even when nothing was affected,
so a 0 in the log proves the check ran.

    reviews, log = clean(load_csv("tests/fixtures/dirty_sample.csv"))
"""

import hashlib
import json
from datetime import date

import numpy as np
import pandas as pd

SOURCE_AMAZON = "amazon_2023_electronics"
SOURCE_SYNTHETIC = "synthetic"

EARLIEST_DATE = pd.Timestamp("1995-01-01")
# Last date a source can contain. Anything later is an invalid date (R4).
COLLECTION_END = {SOURCE_AMAZON: pd.Timestamp("2023-12-31")}

COLUMNS = [
    "review_id", "product_id", "rating", "review_date", "verified_purchase",
    "review_text", "review_title", "reviewer_id", "helpful_votes", "source",
    "pattern", "is_manipulated_product", "is_injected",
]
LABEL_COLUMNS = ["pattern", "is_manipulated_product", "is_injected"]

LOG_COLUMNS = ["step", "rule", "column", "action", "rows_affected", "example_ids", "source", "detail"]

VERIFIED_VALUES = {"true": "verified", "verified": "verified",
                   "false": "unverified", "unverified": "unverified"}

# R8 thresholds on the number of valid ratings
TOO_SMALL = 5     # below this, sample-based signals are "not measured"
SMALL = 20        # below this, excluded from cross-product comparisons


# ---------------------------------------------------------------- loaders

def make_review_id(user_id, parent_asin, timestamp):
    """Stable ID for an Amazon review (DATA_DICTIONARY.md section 3)."""
    key = f"{user_id}|{parent_asin}|{timestamp}".encode("utf-8")
    return "AMZ-" + hashlib.sha1(key).hexdigest()[:16]


def load_amazon_jsonl(path, nrows=None):
    """Read Amazon Reviews 2023 JSON Lines into our column names, values still raw."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if nrows is not None and i >= nrows:
                break
            r = json.loads(line)
            rows.append({
                "review_id": make_review_id(r.get("user_id"), r.get("parent_asin"), r.get("timestamp")),
                "product_id": r.get("parent_asin"),
                "rating": r.get("rating"),
                "review_date": r.get("timestamp"),
                "verified_purchase": r.get("verified_purchase"),
                "review_text": r.get("text"),
                "review_title": r.get("title"),
                "reviewer_id": r.get("user_id"),
                "helpful_votes": r.get("helpful_vote"),
            })
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["source"] = SOURCE_AMAZON
    return _suffix_id_collisions(df)


def _suffix_id_collisions(df):
    """Same review_id but different text: not a duplicate, so give later ones -2, -3, ..."""
    dup = df["review_id"].duplicated(keep=False)
    if not dup.any():
        return df
    text = df["review_text"].fillna("")
    first_text = text.groupby(df["review_id"]).transform("first")
    clash = dup & (text != first_text)
    rank = clash.groupby(df["review_id"]).cumsum()
    df.loc[clash, "review_id"] = df.loc[clash, "review_id"] + "-" + (rank[clash] + 1).astype(str)
    df.attrs["id_collisions"] = int(clash.sum())
    return df


def load_csv(path, source=None):
    """Read a review CSV (synthetic data or a fixture) with every value as raw text."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    if source is not None:
        df["source"] = source
    return df[COLUMNS]


# ---------------------------------------------------------------- helpers

def sample_status(n_rated):
    """R8: 'too_small' (< 5 valid ratings), 'small' (5-19) or 'ok' (>= 20)."""
    if n_rated < TOO_SMALL:
        return "too_small"
    if n_rated < SMALL:
        return "small"
    return "ok"


def _missing(series):
    """True where a value is NA or only whitespace."""
    return series.isna() | series.astype("string").str.strip().eq("")


class _Log:
    def __init__(self, sources):
        self.rows = []
        self.source = ";".join(sorted(map(str, sources)))

    def add(self, rule, column, action, mask_or_count, ids=None, detail=""):
        if isinstance(mask_or_count, (int, np.integer)):
            n, examples = int(mask_or_count), ""
        else:
            n = int(mask_or_count.sum())
            examples = ";".join(map(str, ids[mask_or_count].dropna().head(5))) if ids is not None else ""
        self.rows.append({"step": len(self.rows) + 1, "rule": rule, "column": column,
                          "action": action, "rows_affected": n, "example_ids": examples,
                          "source": self.source, "detail": detail})

    def frame(self):
        return pd.DataFrame(self.rows, columns=LOG_COLUMNS)


# ---------------------------------------------------------------- rules

def _parse_dates(raw, log, ids):
    """R7: Unix ms (11-13 digits), Unix s (9-10 digits) or ISO text -> calendar date.

    Digit counts, not exactly 13 / 10: a review from 1999 is 12 digits in ms
    (1995-01-01 = 788918400000) and 9 digits in seconds (788918400).
    """
    text = raw.astype("string").str.strip()
    text = text.str.replace(r"\.0$", "", regex=True)   # 1658185117948.0 read as a float
    is_ms = text.str.fullmatch(r"\d{11,13}").fillna(False)
    is_s = text.str.fullmatch(r"\d{9,10}").fillna(False)
    out = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    out[is_ms] = pd.to_datetime(text[is_ms].astype("int64"), unit="ms")
    out[is_s] = pd.to_datetime(text[is_s].astype("int64"), unit="s")
    rest = ~(is_ms | is_s) & text.notna()
    out[rest] = pd.to_datetime(text[rest], format="ISO8601", errors="coerce", utc=True).dt.tz_localize(None)
    log.add("R7_date_normalized", "review_date", "normalized", is_ms, ids, "from Unix milliseconds")
    log.add("R7_date_normalized", "review_date", "normalized", is_s, ids, "from Unix seconds")
    return out.dt.normalize()


def clean(raw):
    """Apply rules R7, R4, R3, R1, R2, R5, R6, R0 and R8. Returns (reviews, log)."""
    df = raw.copy().reset_index(drop=True)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS]
    log = _Log(df["source"].dropna().unique())
    ids = df["review_id"]

    for col in ["review_text", "review_title", "reviewer_id", "product_id", "review_id"]:
        df[col] = df[col].astype("string").str.strip()

    # R7 then R4: dates
    raw_date_missing = _missing(df["review_date"])
    df["review_date"] = _parse_dates(df["review_date"], log, ids)
    end = df["source"].map(COLLECTION_END).fillna(pd.Timestamp(date.today()))
    invalid = df["review_date"].isna() | (df["review_date"] < EARLIEST_DATE) | (df["review_date"] > end)
    df.loc[invalid, "review_date"] = pd.NaT
    log.add("R4_invalid_date", "review_date", "excluded_from_time", invalid, ids,
            f"{int((invalid & raw_date_missing).sum())} missing, "
            f"{int((invalid & ~raw_date_missing).sum())} unparseable or out of range")

    # R3: duplicates, the only rule that removes rows
    has_id = df["review_id"].notna()
    dup_a = has_id & df["review_id"].duplicated(keep="first")
    log.add("R3_duplicate", "review_id", "removed", dup_a, df["review_id"], "key (a): same review_id")
    df = df[~dup_a]
    key_b = ["reviewer_id", "product_id", "review_text", "review_date"]
    complete = df[key_b].notna().all(axis=1) & ~_missing(df["review_text"])
    dup_b = complete & df.duplicated(subset=key_b, keep="first")
    log.add("R3_duplicate", "review_text", "removed", dup_b, df["review_id"],
            "key (b): same reviewer + product + text + date")
    df = df[~dup_b].reset_index(drop=True)
    ids = df["review_id"]

    # R1 / R2: ratings. R2 is counted on the raw value, before R1 adds its own NAs.
    raw_rating = df["rating"]
    rating_missing = _missing(raw_rating)
    number = pd.to_numeric(raw_rating.astype("string").str.strip(), errors="coerce")
    out_of_range = ~rating_missing & ~number.isin([1, 2, 3, 4, 5])
    df["rating"] = number.where(~out_of_range & ~rating_missing).astype("Int64")
    log.add("R1_rating_out_of_range", "rating", "excluded_from_rating", out_of_range, ids)
    log.add("R2_rating_missing", "rating", "excluded_from_rating", rating_missing, ids)

    # R5: verification, missing stays "unknown"
    mapped = df["verified_purchase"].astype("string").str.strip().str.lower().map(VERIFIED_VALUES)
    unknown = mapped.isna()
    df["verified_purchase"] = pd.Categorical(mapped.fillna("unknown"),
                                             categories=["verified", "unverified", "unknown"])
    log.add("R5_verification_unknown", "verified_purchase", "set_unknown", unknown, ids)

    # R6: missing text (synthetic data has no text, so it is not checked there)
    synthetic = df["source"].eq(SOURCE_SYNTHETIC)
    no_text = _missing(df["review_text"]) & ~synthetic
    df.loc[_missing(df["review_text"]), "review_text"] = pd.NA
    df.loc[_missing(df["review_title"]), "review_title"] = pd.NA
    log.add("R6_text_missing", "review_text", "excluded_from_text", no_text, ids,
            "skipped for synthetic rows (no text column)" if synthetic.any() else "")

    # helpful votes: missing stays NA, never 0
    df["helpful_votes"] = pd.to_numeric(df["helpful_votes"], errors="coerce").astype("Int64")

    # R0: missing identifiers are flagged, rows kept
    log.add("R0_missing_product_id", "product_id", "flagged", _missing(df["product_id"]), ids)
    log.add("R0_missing_review_id", "review_id", "flagged", _missing(df["review_id"]), ids)
    if raw.attrs.get("id_collisions"):
        log.add("R0_review_id_collision", "review_id", "flagged", raw.attrs["id_collisions"],
                detail="same user + product + time but different text; suffixed -2, -3, ...")

    # ground-truth labels in synthetic data come back from CSV as text
    for col in ["is_manipulated_product", "is_injected"]:
        df[col] = df[col].astype("string").str.lower().map({"true": True, "false": False}).astype("boolean")

    # R8: product-level sample size (counts products, not rows)
    n_rated = df[df["product_id"].notna()].groupby("product_id")["rating"].count()
    status = n_rated.map(sample_status)
    for value in ["too_small", "small"]:
        log.add(f"R8_low_sample_{value}", "product_id", "flagged", int((status == value).sum()),
                detail=f"products with {'< 5' if value == 'too_small' else '5-19'} valid ratings")

    return df, log.frame()


def save_log(log, path):
    log.to_csv(path, index=False)
