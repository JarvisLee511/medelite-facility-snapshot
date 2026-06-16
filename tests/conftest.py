"""Shared fixtures. Tests are network-free: they use a synthetic snapshot that
mirrors the shape of cms_client.get_snapshot() so we never hit the live CMS API."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def snap():
    return {
        "ccn": "686123",
        "state": "FL",
        "legal_name": "Kendall Lakes Healthcare and Rehab Center",
        "address": "5280 SW 157 Avenue, Miami, FL",
        "certified_beds": "150",
        "avg_residents_per_day": "142.4",
        "ratings": {"overall": "5", "health_inspection": "5",
                    "staffing": "2", "quality": "5"},
        "care_compare_url": ("https://www.medicare.gov/care-compare/details/"
                             "nursing-home/686123/view-all?state=FL"),
        "processing_date": "2026-05-01",
        "hospitalization": {
            ("STR", "hosp"): {"facility": "25.5", "state": "26.2", "nation": "23.9"},
            ("STR", "ed"): {"facility": "8.0", "state": "9.2", "nation": "12.0"},
            ("LT", "hosp"): {"facility": "2.75", "state": "2.15", "nation": "1.90"},
            ("LT", "ed"): {"facility": "0.91", "state": "1.16", "nation": "1.80"},
        },
    }


@pytest.fixture
def manual_full():
    return {"name_override": "", "emr": "PCC", "current_census": "112",
            "patient_type": "Long-term & Short-term", "prev_coverage": "Yes",
            "prev_performance": "About 30 patients/day",
            "medical_coverage": "Optometry, PCP, Podiatry"}
