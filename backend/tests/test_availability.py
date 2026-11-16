"""Tests for availability requirement reader."""

import pytest
from whichcloud.availability import classify_availability, read_availability


# The 4 prompt examples specified in master prompt
def test_retail_business_hours_example():
    text = "must not go down during business hours because billing stops"
    cls, evidence = classify_availability(text)
    assert cls == "business_hours"
    assert "business hours" in evidence


def test_payments_always_on_example():
    text = "we need 24/7 uptime for our payments API"
    cls, evidence = classify_availability(text)
    assert cls == "always_on"
    assert "24/7" in evidence


def test_regulated_dr_example():
    text = "regulator requires disaster recovery within India"
    cls, evidence = classify_availability(text)
    assert cls == "regulated_dr"
    assert "disaster recovery" in evidence


def test_internal_tool_standard_example():
    text = "simple internal tool, downtime is fine"
    cls, evidence = classify_availability(text)
    assert cls == "standard"
    assert "downtime is fine" in evidence


# 6 additional edge cases
def test_edge_case_24x7_variant():
    text = "Online shopping store with 24x7 availability across all devices"
    assert read_availability(text) == "always_on"


def test_edge_case_mission_critical():
    text = "Hospital clinical portal, mission critical emergency triage records"
    assert read_availability(text) == "always_on"


def test_edge_case_rto_rpo_mentions():
    text = "Fintech lending platform with strict compliance requiring RTO under 15 minutes and low RPO"
    assert read_availability(text) == "regulated_dr"


def test_edge_case_working_hours():
    text = "POS billing software operating store hours, cannot go down during working hours"
    assert read_availability(text) == "business_hours"


def test_edge_case_batch_unstated():
    text = "Nightly batch data processing pipeline running once a day over logs"
    assert read_availability(text) == "standard"


def test_edge_case_unstated_and_empty():
    assert read_availability("") == "standard"
    assert read_availability("   ") == "standard"
    assert read_availability("a python web app with postgres and redis") == "standard"


def test_downtime_is_fine_overrules_always_available():
    # If someone says "we don't need always on, downtime is fine", it must be standard
    text = "Internal dashboard, downtime is fine if it goes down"
    assert read_availability(text) == "standard"

