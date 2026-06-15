"""
app.py — Facility Assessment Snapshot (Streamlit micro-app)
-----------------------------------------------------------
Enter a CCN -> pull live CMS public data -> combine with manual operational
inputs -> preview -> download a polished PDF / Word report.

Architecture: this file is UI only. All CMS access lives in cms_client.py and
all document rendering lives in report.py, so the app stays thin and testable.
The CMS API is called server-side here, so there is no browser CORS issue.
"""

import html
import re

import plotly.graph_objects as go
import streamlit as st

import cms_client as c
import report as rpt

st.set_page_config(page_title="Facility Assessment Snapshot",
                   page_icon="🏥", layout="wide")


def _num(v):
    """Coerce an API string value to float for charting; None if not numeric."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _preview_table_html(rows):
    """Render the report rows as a clean, section-grouped clinical HTML table."""
    # rows are fixed order: 0-8 profile, 9-12 ratings, 13-24 hospitalization
    sections = [(0, "Facility Profile"), (9, "CMS Star Ratings"),
                (13, "Hospitalization & ED Metrics")]
    starts = dict(sections)
    out = ["<table class='snap-table'><tr><th>Field</th><th>Value</th></tr>"]
    for i, (label, value) in enumerate(rows):
        if i in starts:
            out.append(f"<tr class='snap-sec'><td>{starts[i]}</td><td></td></tr>")
        out.append(f"<tr><td class='lbl'>{html.escape(str(label))}</td>"
                   f"<td>{html.escape(str(value))}</td></tr>")
    out.append("</table>")
    return "".join(out)

# --- branding (hard-coded; never overwritten by facility data) ---------------
# Light, clinical look: soft blue-white canvas + medical teal/blue accents.
# The INFINITE / MEDELITE banner colors are brand-locked and kept as-is.
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Work+Sans:wght@300;400;500;600;700;800&display=swap');
      /* MedElite brand palette (from medelitegrp.com) */
      :root { --me-blue:#3993CB; --me-deep:#066AAB; --me-green:#00D084;
              --me-ink:#32373C; }
      html, body, [class*="css"], .stApp, button, input, textarea, select {
        font-family: 'Work Sans', -apple-system, sans-serif !important; }
      .stApp { background:
        linear-gradient(180deg,#E8F2FA 0%, #F4F9FD 240px, #FFFFFF 560px); }
      .block-container { padding-top: 1.4rem; }

      .me-topbar { height:6px; border-radius:6px; margin-bottom:14px;
        background:linear-gradient(90deg,#3993CB 0%, #066AAB 55%, #00D084 100%); }

      .brand-card { background:#FFFFFF; border:1px solid #DCEBF1;
        border-radius:16px; padding:16px 20px 12px; text-align:center;
        box-shadow:0 6px 20px rgba(57,147,203,.12); }
      .brand-infinite { font-size:36px; font-weight:800; color:#D6007E;
        letter-spacing:1px; line-height:1; }
      .brand-sub { font-size:15px; font-weight:700; color:#066AAB; margin-top:-1px; }
      .brand-tag { color:#3993CB; font-size:11px; font-weight:700;
        letter-spacing:3px; margin-top:8px; text-transform:uppercase; }

      .report-title { text-align:center; font-weight:800; font-size:20px;
        color:var(--me-ink); margin-top:14px; }
      .report-state { text-align:center; font-weight:700; color:var(--me-blue);
        letter-spacing:2px; margin-bottom:6px; }

      /* section headings get a brand-blue left-accent bar */
      h3 { border-left:5px solid #3993CB; padding-left:10px; color:var(--me-deep)
           !important; font-weight:700; }

      /* star-rating metric cards -> clean blue cards */
      div[data-testid="stMetric"] { background:#F1F7FC; border:1px solid #D2E6F4;
        border-radius:12px; padding:10px 8px; text-align:center; }
      div[data-testid="stMetricValue"] { color:#066AAB; }

      .stButton>button, .stDownloadButton>button {
        border-radius:10px; font-weight:600; }

      /* custom preview table */
      .snap-table { width:100%; border-collapse:collapse; font-size:13.5px;
        border:1px solid #D2E6F4; border-radius:12px; overflow:hidden; }
      .snap-table th { background:#3993CB; color:#fff; text-align:left;
        padding:8px 12px; font-weight:700; }
      .snap-table td { padding:7px 12px; border-top:1px solid #E8F1F8; }
      .snap-table td.lbl { font-weight:600; color:var(--me-ink); width:58%; }
      .snap-table tr:nth-child(even) td { background:#F6FAFD; }
      .snap-sec td { background:#E6F1F9 !important; font-weight:700;
        color:#066AAB; letter-spacing:.5px; text-transform:uppercase;
        font-size:11.5px; }
    </style>
    <div class="me-topbar"></div>
    <div class="brand-card">
      <div class="brand-infinite">INFINITE</div>
      <div class="brand-sub">Managed by MEDELITE</div>
      <div class="brand-tag">&#9877;&nbsp; Healthcare Facility Intelligence</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- CCN lookup --------------------------------------------------------------
col_in, col_btn = st.columns([4, 1])
with col_in:
    ccn = st.text_input("CMS Certification Number (CCN)",
                        placeholder="e.g. 686123  (Kendall Lakes Healthcare and Rehab Center, FL)",
                        max_chars=6).strip()
with col_btn:
    st.write("")
    st.write("")
    lookup = st.button("🔍 Fetch facility", use_container_width=True)

if lookup:
    if not re.fullmatch(r"[A-Za-z0-9]{6}", ccn):
        st.error("A CCN is exactly 6 characters (digits/letters). Please check the value.")
    else:
        try:
            with st.spinner("Querying CMS Provider Data Catalog…"):
                st.session_state["snap"] = c.get_snapshot(ccn)
            st.session_state["ccn"] = ccn
        except c.FacilityNotFound:
            st.session_state.pop("snap", None)
            st.error(f"No CMS facility found for CCN '{ccn}'. Double-check the number.")
        except Exception as e:  # network / API / parsing
            st.session_state.pop("snap", None)
            st.error(f"Could not reach the CMS API or parse its response: {e}")

snap = st.session_state.get("snap")

# --- main: inputs (left) + live preview (right) ------------------------------
if not snap:
    st.info("Enter a valid CCN above and click **Fetch facility** to begin. "
            "Try **686123** for the sample facility.")
    st.stop()

left, right = st.columns([1, 1.35], gap="large")

with left:
    st.subheader("Manual Operational Inputs")
    st.caption("Internal metrics that don't live in the public CMS database.")
    name_override = st.text_input(
        "Facility Name Override (optional)",
        placeholder=snap["legal_name"],
        help="Leave blank to use the official CMS legal name shown as the placeholder.")
    emr = st.text_input("EMR", placeholder="e.g. PCC, MatrixCare")
    current_census = st.text_input("Current Census", placeholder="e.g. 112")
    patient_type = st.text_input("Type of Patient",
                                 placeholder="e.g. Long-term & Short-term")
    prev_coverage = st.selectbox("Previous Coverage from Medelite", ["", "Yes", "No"])
    prev_performance = st.text_input("Previous Provider Performance from Medelite",
                                     placeholder="e.g. About 30 patients/day")
    medical_coverage = st.text_input("Medical Coverage",
                                     placeholder="e.g. Optometry, PCP, Podiatry")

manual = {
    "name_override": name_override,
    "emr": emr,
    "current_census": current_census,
    "patient_type": patient_type,
    "prev_coverage": prev_coverage,
    "prev_performance": prev_performance,
    "medical_coverage": medical_coverage,
}

with right:
    st.markdown(f"<div class='report-title'>{rpt.REPORT_TITLE}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-state'>{snap['state']}</div>", unsafe_allow_html=True)

    # star ratings as quick metric cards
    r = snap["ratings"]
    m1, m2, m3, m4 = st.columns(4)
    for col, label, key in [(m1, "Overall", "overall"), (m2, "Health Insp.", "health_inspection"),
                            (m3, "Staffing", "staffing"), (m4, "Quality", "quality")]:
        val = r.get(key) or "N/A"
        stars = "★" * int(val) + "☆" * (5 - int(val)) if str(val).isdigit() else ""
        col.metric(label, f"{val}/5" if str(val).isdigit() else "N/A", stars)

    # full report preview table (section-grouped, clinical styling)
    rows = rpt.build_report_rows(snap, manual)
    st.markdown(_preview_table_html(rows), unsafe_allow_html=True)

# --- bonus: hospitalization / ED comparison charts ---------------------------
hosp = snap.get("hospitalization")
if hosp:
    st.divider()
    st.subheader("Hospitalization & ED Metrics — facility vs. benchmarks")
    cc1, cc2 = st.columns(2)

    def _bar(container, title, keys, suffix):
        labels = {("STR", "hosp"): "STR Hospitalization", ("STR", "ed"): "STR ED Visit",
                  ("LT", "hosp"): "LT Hospitalization", ("LT", "ed"): "LT ED Visit"}
        cats = [labels[k] for k in keys]
        fig = go.Figure()
        for series, color in [("facility", "#3993CB"), ("state", "#00D084"),
                              ("nation", "#9FB3C8")]:
            fig.add_bar(name=series.capitalize(), x=cats,
                        y=[_num(hosp[k][series]) for k in keys],
                        marker_color=color)
        fig.update_layout(barmode="group", title=title, height=340,
                          yaxis_title=suffix, legend_title_text="",
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          font=dict(color="#13354B"),
                          margin=dict(t=40, b=10, l=10, r=10))
        container.plotly_chart(fig, use_container_width=True)

    _bar(cc1, "Short-stay measures (%)", [("STR", "hosp"), ("STR", "ed")], "%")
    _bar(cc2, "Long-stay measures (per 1,000 resident-days)",
         [("LT", "hosp"), ("LT", "ed")], "per 1,000")

# --- downloads + provenance --------------------------------------------------
st.divider()
display_name = rpt.resolve_display_name(snap, manual)
safe = re.sub(r"[^A-Za-z0-9]+", "_", display_name).strip("_") or "facility"
d1, d2, d3 = st.columns([1, 1, 2])
d1.download_button("⬇️ Download PDF", data=rpt.render_pdf(snap, manual),
                   file_name=f"{safe}_Facility_Assessment_Snapshot.pdf",
                   mime="application/pdf", use_container_width=True)
d2.download_button("⬇️ Download Word", data=rpt.render_docx(snap, manual),
                   file_name=f"{safe}_Facility_Assessment_Snapshot.docx",
                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   use_container_width=True)
with d3:
    st.markdown(f"[View official CMS Care Compare profile →]({snap['care_compare_url']})")
    st.caption(f"Data as of {snap['processing_date']} · Source: CMS Provider Data "
               "Catalog (data.cms.gov)")
