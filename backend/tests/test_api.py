"""Tests for the API handlers (valid and invalid input)."""

from __future__ import annotations

import json

import pytest

from travel_advisor import api


# --------------------------- routes -------------------------------------- #

def test_get_routes_lists_labels():
    status, body = api.get_routes({})
    assert status == 200
    assert len(body["routes"]) >= 5
    first = body["routes"][0]
    assert "code" in first and "label" in first
    # label is human-friendly: contains the city and the code
    assert "(" in first["label"] and ")" in first["label"]


# --------------------------- price --------------------------------------- #

def test_get_price_valid():
    status, body = api.get_price({"route": "MXP-BCN", "date": "2026-03-02"})
    assert status == 200
    assert body["route"] == "MXP-BCN"
    assert "price" in body and "factors" in body
    assert isinstance(body["factors"], list)


def test_get_price_missing_param():
    with pytest.raises(api.BadRequest):
        api.get_price({"route": "MXP-BCN"})  # no date


def test_get_price_bad_date():
    with pytest.raises(api.BadRequest):
        api.get_price({"route": "MXP-BCN", "date": "not-a-date"})


def test_get_price_unknown_route():
    with pytest.raises(api.BadRequest):
        api.get_price({"route": "ZZZ-ZZZ", "date": "2026-03-02"})


# --------------------------- growth -------------------------------------- #

def test_get_growth_valid():
    status, body = api.get_growth({"budget": "100000"})
    assert status == 200
    assert body["markets"] and body["allocations"]
    # allocations sum to budget
    total = sum(float(a["amount"]) for a in body["allocations"])
    assert abs(total - 100000.0) < 0.01
    # markets are ranked by descending score
    scores = [m["score"] for m in body["markets"]]
    assert scores == sorted(scores, reverse=True)


def test_get_growth_includes_ad_breakdown_summing_to_allocation():
    from decimal import Decimal

    status, body = api.get_growth({"budget": "100000"})
    assert status == 200
    assert body["breakdowns"]
    by_market_alloc = {a["market"]: a["amount"] for a in body["allocations"]}
    for bd in body["breakdowns"]:
        channel_sum = sum(Decimal(c["amount"]) for c in bd["channels"])
        assert channel_sum == Decimal(by_market_alloc[bd["market"]])
        assert bd["keywords"]  # each market lists example keywords


def test_get_growth_context_boosts_focused_market():
    """A route/date context demand-boosts that route's market's score."""
    plain = api.get_growth({"budget": "100000"})[1]
    # Dublin around St. Patrick's Day: holiday + event -> uplift > 1.
    ctx = api.get_growth(
        {"budget": "100000", "route": "MXP-DUB", "date": "2026-03-15", "days": "8"}
    )[1]
    assert ctx["focusMarket"] == "DUB"
    assert ctx["focusUplift"] > 1.0
    dub_plain = next(m["score"] for m in plain["markets"] if m["market"] == "DUB")
    dub_ctx = next(m["score"] for m in ctx["markets"] if m["market"] == "DUB")
    assert dub_ctx > dub_plain
    assert any(m["focused"] for m in ctx["markets"])


def test_get_growth_negative_budget():
    with pytest.raises(api.BadRequest):
        api.get_growth({"budget": "-5"})


def test_get_growth_bad_budget():
    with pytest.raises(api.BadRequest):
        api.get_growth({"budget": "abc"})


# --------------------------- storyline ----------------------------------- #

def test_get_storyline_valid():
    status, body = api.get_storyline(
        {"route": "MXP-BCN", "date": "2026-03-02", "budget": "100000"}
    )
    assert status == 200
    assert isinstance(body["storyline"], list) and body["storyline"]


# --------------------------- lambda adapters ----------------------------- #

def test_lambda_price_shape():
    event = {"queryStringParameters": {"route": "MXP-BCN", "date": "2026-03-02"}}
    resp = api.lambda_price(event)
    assert resp["statusCode"] == 200
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    body = json.loads(resp["body"])
    assert body["route"] == "MXP-BCN"


def test_lambda_price_bad_input_returns_400():
    event = {"queryStringParameters": {"route": "MXP-BCN"}}  # no date
    resp = api.lambda_price(event)
    assert resp["statusCode"] == 400
    assert "error" in json.loads(resp["body"])
