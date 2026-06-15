# Facility Assessment Snapshot

A lightweight web micro-app that turns a single **CCN (CMS Certification Number)**
into a polished, print-ready facility assessment report. Enter a CCN → the app
pulls **live** public data from the CMS Provider Data Catalog, combines it with
manual operational inputs, and exports a one-page **PDF** (and an editable
**Word** document) — with a clickable link back to the official Medicare
Care Compare profile.

> Built for the Medelite technical case study (Facility Assessment Report Generator).

**🔗 Live app:** https://medelite-facility-snapshot.streamlit.app/
**💻 Repository:** https://github.com/JarvisLee511/medelite-facility-snapshot

**Validation target — CCN `686123` (Kendall Lakes Healthcare and Rehab Center, FL):**
the facility name, address, state, CCN, the report layout, and the Care Compare
source URL all match the provided sample exactly. The star ratings, certified-bed
count, and hospitalization/ED figures reflect the **current** CMS data (stamped
*Data as of 2026-05-01*) and therefore differ from the sample, which was generated
from an earlier CMS refresh — see Assumption #1 below.

---

## Features

### Core MVP
- **Dynamic CCN lookup** — query any valid CCN against the live CMS API.
- **Data engine** — fetches location, the four star ratings, certified beds, and
  metadata from the CMS Provider Data Catalog.
- **Facility name override** — defaults to the official CMS legal name; an optional
  field lets a user supply an internal/localized name that overrides it on output.
- **Manual operational inputs** — EMR, Current Census, Type of Patient, Medelite
  coverage/history, and medical coverage (fields that don't exist in CMS data).
- **One-click PDF export** — a clean, print-ready report that downloads instantly.
- **Dynamic Medicare source hyperlink** — the report embeds a clickable link to
  `medicare.gov/care-compare/.../{CCN}`, with the CCN injected dynamically.
- **Live deployment** on Streamlit Community Cloud.

### Bonus (all implemented)
- **All 12 hospitalization / ED metrics** — the four claims-based measures
  (short-stay & long-stay hospitalization + outpatient ED) for the facility,
  each shown against its **state** and **national** averages.
- **Editable Word (.docx) export** — second download button.
- **Interactive charts** — Plotly grouped bars comparing facility vs. state vs.
  national for short-stay (%) and long-stay (per-1,000) measures.
- **Robust error handling** — invalid/short CCN, facility-not-found, and CMS API
  failures all surface clean, specific messages instead of crashing.

---

## Data sources (CMS Provider Data Catalog)

| Purpose | Dataset | Distribution ID |
|---|---|---|
| Name, address, beds, star ratings | Provider Information | `588f22e8-145d-5db5-baff-f59ce253316c` |
| Facility hospitalization/ED measures | Medicare Claims Quality Measures | `19fa35fb-11f0-5ed8-999e-52f272a25b01` |
| State & national averages | State US Averages | `03e812a4-7576-5b9b-8cd7-2135649118f4` |

All three are queried server-side via the PDC datastore query endpoint
(`https://data.cms.gov/provider-data/api/1/datastore/query/{distribution}`).

---

## Engineering decisions

- **Server-side API calls (no CORS).** The CMS API is called from Python, not the
  browser, so cross-origin restrictions never apply.
- **Single source of truth for exports.** `report.build_report_rows()` produces the
  ordered (label, value) list used by *both* the PDF and the Word renderer, so the
  two formats can never drift apart.
- **Resilient column mapping.** In the averages file, the four claims measures are
  stored as wide columns whose names carry a CMS-generated hash suffix (e.g.
  `..._1d02`) that can change on a data refresh. They are resolved **dynamically by
  a stable descriptive prefix** rather than hard-coded, so a refresh won't break the app.
- **Embedded Unicode font.** The PDF embeds DejaVu Sans so the exact banner
  (`INFINITE — Managed by MEDELITE`, with an em dash) and any special characters in
  facility names render reliably across platforms.
- **Branding guardrail.** The platform banner `INFINITE — Managed by MEDELITE` is a
  hard-coded constant and is **never** replaced by the CMS/override facility name;
  the facility name appears only in the report body under "Name of Facility".

---

## Assumptions (documented per the brief)

1. **Live data vs. the sample PDF.** The provided `Kendall Lakes` sample reflects an
   earlier CMS data refresh; CMS recalculates star ratings and measures periodically
   (the dictionary is dated Feb 2026, and the data carries a `2026-05-01` processing
   date). This app **dynamically reflects the current official data**, so its star
   ratings / beds differ from the static sample. Hard-coding the sample values to
   "match" would defeat the core requirement to *dynamically fetch live public data*,
   so the report instead stamps **"Data as of {processing date}"** for transparency.
2. **Current Census = manual input.** The blank template labels Current Census as
   `{Average Number of Residents per Day}` (an API field), but the brief's mapping
   table lists it as a **Manual Input**. The brief's mapping table is treated as
   authoritative, so Current Census is a user-entered field.
3. **Claims measures use the risk-adjusted score** (`adjusted_score`), matching what
   Care Compare publicly reports; the raw observed score is also retrieved.
4. **Text normalization.** CMS stores names/addresses in ALL CAPS; they are converted
   to clean Title Case (preserving directionals like `SW` and not inventing ordinal
   suffixes — `157` stays `157`).
5. **Averages mapping.** State averages come from the `State US Averages` row matching
   the facility's state; national averages come from the `NATION` row.

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL and try CCN **`686123`** (Kendall Lakes Healthcare and
Rehab Center, FL — the case study's validation facility).

---

## Project structure

```
medelite-facility-snapshot/
├── app.py            # Streamlit UI (thin; no business logic)
├── cms_client.py     # CMS Provider Data Catalog access + field mapping
├── report.py         # PDF (fpdf2) + Word (python-docx) renderers
├── assets/fonts/     # bundled DejaVu Sans (Unicode PDF font)
├── requirements.txt
└── README.md
```

## Tech stack
Python · Streamlit · fpdf2 · python-docx · Plotly · requests · CMS Provider Data Catalog API
