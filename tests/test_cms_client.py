"""Unit tests for the data-layer helpers (no network)."""

import cms_client as c


def test_smart_title_keeps_directionals_and_small_words():
    assert c.smart_title("KENDALL LAKES HEALTHCARE AND REHAB CENTER") == \
        "Kendall Lakes Healthcare and Rehab Center"
    assert c.smart_title("5280 SW 157 AVENUE") == "5280 SW 157 Avenue"
    assert c.smart_title("") == ""


def test_fmt_metric_units():
    assert c.fmt_metric("25.5", "STR_PCT") == "25.5%"
    assert c.fmt_metric("2.75", "LT") == "2.75"
    assert c.fmt_metric(None, "LT") == "N/A"
    assert c.fmt_metric("", "STR_PCT") == "N/A"


def test_care_compare_url_format():
    assert c.CARE_COMPARE_URL.format(ccn="686123", state="FL") == (
        "https://www.medicare.gov/care-compare/details/"
        "nursing-home/686123/view-all?state=FL")


def test_resolve_avg_columns_matches_by_prefix_despite_hash_suffix():
    row = {
        "percentage_of_short_stay_residents_who_were_rehospitalized__1d02": "1",
        "percentage_of_short_stay_residents_who_had_an_outpatient_em_d911": "2",
        "number_of_hospitalizations_per_1000_longstay_resident_days": "3",
        "number_of_outpatient_emergency_department_visits_per_1000_l_de9d": "4",
        "state_or_nation": "NATION", "unrelated_column": "x",
    }
    resolved = c._resolve_avg_columns(row)
    assert resolved[("STR", "hosp")].startswith("percentage_of_short_stay_residents_who_were_rehospitalized")
    assert resolved[("STR", "ed")].startswith("percentage_of_short_stay_residents_who_had_an_outpatient_em")
    assert resolved[("LT", "hosp")] == "number_of_hospitalizations_per_1000_longstay_resident_days"
    assert resolved[("LT", "ed")].startswith("number_of_outpatient_emergency_department_visits_per_1000_l")


def test_claims_measures_cover_the_four_snapshot_metrics():
    # the 4 measure codes that build the 12 hospitalization/ED lines
    assert set(c.CLAIMS_MEASURES) == {"521", "522", "551", "552"}
