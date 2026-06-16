"""Unit tests for the report layer (PDF + Word), network-free."""

import io
import re

from pypdf import PdfReader

import report as rpt


def test_build_report_rows_count_and_order(snap, manual_full):
    rows = rpt.build_report_rows(snap, manual_full)
    assert len(rows) == 25                       # 13 base + 12 hospitalization
    assert rows[0][0] == "Name of Facility"
    assert dict(rows)["EMR"] == "PCC"
    assert dict(rows)["Census Capacity"] == "150"
    # the 12 hospitalization/ED labels are present
    assert len([k for k, _ in rows
                if "Hospitalization" in k or "ED Visit" in k]) == 12


def test_blank_manual_fields_render_as_dash(snap):
    rows = dict(rpt.build_report_rows(snap, {}))
    assert rows["EMR"] == "—"
    assert rows["Current Census"] == "—"


def test_name_override(snap):
    assert rpt.resolve_display_name(snap, {}) == "Kendall Lakes Healthcare and Rehab Center"
    assert rpt.resolve_display_name(snap, {"name_override": "Internal Name"}) == "Internal Name"


def test_render_pdf_is_valid_single_page_with_link_and_no_openaction(snap, manual_full):
    pdf = rpt.render_pdf(snap, manual_full)
    assert pdf[:4] == b"%PDF"
    assert b"/OpenAction" not in pdf                       # stripped for clean static file
    pages = re.search(rb"/Count\s+(\d+)", pdf)
    assert pages and pages.group(1) == b"1"                # print-ready, one page
    reader = PdfReader(io.BytesIO(pdf))
    uris = [str(a.get_object()["/A"]["/URI"])
            for pg in reader.pages for a in (pg.get("/Annots") or [])
            if a.get_object().get("/A", {}).get("/URI")]
    assert any("686123" in u for u in uris)                # dynamic Care Compare link


def test_branding_guardrail_name_does_not_overwrite_banner(snap):
    pdf = rpt.render_pdf(snap, {"name_override": "ZZZ Custom Facility"})
    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "INFINITE" in text                              # banner intact
    assert "ZZZ Custom Facility" in text                   # name only in the body


def test_render_docx_is_valid_zip(snap, manual_full):
    docx_bytes = rpt.render_docx(snap, manual_full)
    assert docx_bytes[:2] == b"PK"                         # .docx is a zip
    assert len(docx_bytes) > 5000
