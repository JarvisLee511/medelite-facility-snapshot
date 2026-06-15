"""
cms_client.py
-------------
Data layer for the Facility Assessment Snapshot app.

All access to the public CMS Provider Data Catalog (PDC) lives here, isolated
from the UI and the report renderers. The app calls these functions server-side
(Python `requests`), so we never touch the CMS API from the browser -> no CORS.

Three PDC datasets are used:
  * Provider Information        -> name, address, beds, the 4 star ratings
  * Medicare Claims Quality     -> the 4 facility claims measures (STR/LT hosp+ED)
  * State US Averages           -> state + national averages for those 4 measures

Design notes / engineering choices (defensible in the walkthrough):
  * We query by the *distribution UUID*, which is the stable id the datastore
    query endpoint expects (the human-readable dataset id 4pq5-n9py is NOT
    accepted by the conditions endpoint).
  * The averages file stores the 4 claims measures as *wide columns* whose names
    carry a CMS-generated hash suffix (e.g. "..._1d02"). Those suffixes can
    change on a data refresh, so we resolve the columns dynamically by matching
    a stable descriptive prefix instead of hard-coding the volatile names.
  * Care Compare reports the *risk-adjusted* score for claims measures, so we
    surface `adjusted_score` as the facility value (raw `observed_score` kept too).
"""

from __future__ import annotations

import requests

# --- PDC datastore endpoint + dataset distribution ids -----------------------
BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"
DIST_PROVIDER_INFO = "588f22e8-145d-5db5-baff-f59ce253316c"  # Provider Information
DIST_CLAIMS = "19fa35fb-11f0-5ed8-999e-52f272a25b01"         # Medicare Claims Quality Measures
DIST_AVERAGES = "03e812a4-7576-5b9b-8cd7-2135649118f4"        # State US Averages

CARE_COMPARE_URL = (
    "https://www.medicare.gov/care-compare/details/nursing-home/{ccn}/view-all?state={state}"
)

# The 4 claims measures that make up the 12 hospitalization/ED snapshot lines.
# measure_code -> (resident scope, metric kind)
CLAIMS_MEASURES = {
    "521": ("STR", "hosp"),  # short-stay rehospitalization (%)
    "522": ("STR", "ed"),    # short-stay outpatient ED visit (%)
    "551": ("LT", "hosp"),   # long-stay hospitalizations per 1,000 days
    "552": ("LT", "ed"),     # long-stay outpatient ED per 1,000 days
}

# Stable descriptive prefixes used to find the same 4 measures (wide columns)
# in the State US Averages file, regardless of their volatile hash suffix.
AVG_COL_PREFIXES = {
    ("STR", "hosp"): "percentage_of_short_stay_residents_who_were_rehospitalized",
    ("STR", "ed"): "percentage_of_short_stay_residents_who_had_an_outpatient_em",
    ("LT", "hosp"): "number_of_hospitalizations_per_1000_longstay_resident_days",
    ("LT", "ed"): "number_of_outpatient_emergency_department_visits_per_1000_l",
}

TIMEOUT = 30


class FacilityNotFound(Exception):
    """Raised when a CCN returns no Provider Information row."""


def _query(distribution: str, conditions: list[dict] | None = None,
           limit: int | None = None) -> list[dict]:
    """POST a conditions query to the PDC datastore and return result rows."""
    payload: dict = {}
    if conditions:
        payload["conditions"] = conditions
    if limit:
        payload["limit"] = limit
    resp = requests.post(f"{BASE}/{distribution}", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _eq(prop: str, value: str) -> dict:
    return {"property": prop, "value": value, "operator": "="}


# --- public functions --------------------------------------------------------
def get_provider_info(ccn: str) -> dict:
    """Fetch the Provider Information row for a CCN. Raises FacilityNotFound."""
    rows = _query(DIST_PROVIDER_INFO,
                  [_eq("cms_certification_number_ccn", ccn)], limit=1)
    if not rows:
        raise FacilityNotFound(f"No CMS facility found for CCN '{ccn}'.")
    return rows[0]


def get_claims(ccn: str) -> dict:
    """Return {(scope, kind): {adjusted, observed}} for the 4 claims measures."""
    rows = _query(DIST_CLAIMS, [_eq("cms_certification_number_ccn", ccn)])
    out: dict = {}
    for r in rows:
        key = CLAIMS_MEASURES.get(str(r.get("measure_code")))
        if key:
            out[key] = {
                "adjusted": r.get("adjusted_score"),
                "observed": r.get("observed_score"),
                "description": r.get("measure_description"),
                "footnote": r.get("footnote_for_score"),
            }
    return out


def _resolve_avg_columns(sample_row: dict) -> dict:
    """Map (scope, kind) -> actual column name in the averages file by prefix."""
    resolved = {}
    for key, prefix in AVG_COL_PREFIXES.items():
        match = next((c for c in sample_row if c.startswith(prefix)), None)
        resolved[key] = match
    return resolved


def get_averages(state: str) -> dict:
    """Return {'state': {(scope,kind): val}, 'nation': {...}} for the 4 measures."""
    rows = _query(DIST_AVERAGES)  # small file: ~52 rows (states + NATION)
    by_region = {r.get("state_or_nation"): r for r in rows}
    cols = _resolve_avg_columns(rows[0]) if rows else {}

    def pick(region_row):
        return {k: (region_row.get(col) if col else None) for k, col in cols.items()}

    nation = by_region.get("NATION", {})
    st = by_region.get(state, {})
    return {"nation": pick(nation), "state": pick(st)}


def get_snapshot(ccn: str, include_claims: bool = True) -> dict:
    """High-level: assemble everything the report needs for one facility.

    Returns a dict with provider fields, the 4 star ratings, the 12-line
    hospitalization block (facility/state/national), and provenance metadata.
    `include_claims=False` skips the bonus block (MVP-only mode).
    """
    info = get_provider_info(ccn)
    state = info.get("state", "")

    snap = {
        "ccn": ccn,
        "state": state,
        "legal_name": smart_title(info.get("provider_name", "")),
        "address": _format_address(info),
        "certified_beds": info.get("number_of_certified_beds", ""),
        "avg_residents_per_day": info.get("average_number_of_residents_per_day", ""),
        "ratings": {
            "overall": info.get("overall_rating", ""),
            "health_inspection": info.get("health_inspection_rating", ""),
            "staffing": info.get("staffing_rating", ""),
            "quality": info.get("qm_rating", ""),  # Quality of Resident Care
        },
        "care_compare_url": CARE_COMPARE_URL.format(ccn=ccn, state=state),
        "processing_date": info.get("processing_date", ""),
        "hospitalization": None,
    }

    if include_claims:
        claims = get_claims(ccn)
        avgs = get_averages(state)
        snap["hospitalization"] = _build_hospitalization_block(claims, avgs)

    return snap


# --- formatting helpers ------------------------------------------------------
# Tokens kept uppercase (directionals/numerals) and small words kept lowercase
# when normalizing CMS's ALL-CAPS text to clean Title Case for the report.
_KEEP_UPPER = {"SW", "SE", "NW", "NE", "N", "S", "E", "W", "II", "III", "IV"}
_SMALL_WORDS = {"and", "of", "the", "for", "at", "by", "on", "in", "to", "a", "an"}


def smart_title(s: str) -> str:
    """Title-case ALL-CAPS source text without mangling directionals/small words.

    e.g. 'KENDALL LAKES HEALTHCARE AND REHAB CENTER' -> 'Kendall Lakes Healthcare
    and Rehab Center'; '5280 SW 157 AVENUE' -> '5280 SW 157 Avenue'. We do NOT
    invent ordinal suffixes (157 stays 157, not 157th) to avoid altering data.
    """
    if not s:
        return s
    out = []
    for i, w in enumerate(s.split()):
        if w.upper() in _KEEP_UPPER:
            out.append(w.upper())
        elif i > 0 and w.lower() in _SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _format_address(info: dict) -> str:
    street = smart_title(info.get("provider_address", ""))
    city = smart_title(info.get("citytown", ""))
    state = info.get("state", "")  # postal abbreviation stays uppercase
    return ", ".join(p for p in (street, city, state) if p)


def _build_hospitalization_block(claims: dict, avgs: dict) -> dict:
    """Assemble the 12 lines: facility value + state avg + national avg x4."""
    block = {}
    for key in CLAIMS_MEASURES.values():  # (STR,hosp),(STR,ed),(LT,hosp),(LT,ed)
        block[key] = {
            "facility": (claims.get(key) or {}).get("adjusted"),
            "state": avgs.get("state", {}).get(key),
            "nation": avgs.get("nation", {}).get(key),
        }
    return block


def fmt_metric(value, kind: str) -> str:
    """STR measures render as percentages (1 dp); LT as per-1,000 (2 dp)."""
    if value in (None, ""):
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{v:.1f}%" if kind == "STR_PCT" else f"{v:.2f}"
