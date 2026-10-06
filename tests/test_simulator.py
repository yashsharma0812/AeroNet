from ipaddress import ip_network

import pytest

from app import app, state
from simulator.addressing import PLAN, addressing_plan, validate_plan
from simulator.state import NetworkState


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    state.reset()
    with app.test_client() as test_client:
        yield test_client


def test_default_direct_route():
    network = NetworkState()
    route = network.snapshot()["route"]
    assert route["router_path"] == ["R-CHECKIN", "R-SERVICES"]
    assert route["cost"] == 10


def test_alternative_route_after_direct_failure():
    network = NetworkState()
    result = network.update_link("checkin-services", {"admin_up": False})
    assert result["route"]["router_path"] == ["R-CHECKIN", "R-CARGO", "R-SERVICES"]
    assert result["route"]["cost"] == 20


def test_unreachable_after_checkin_isolation():
    network = NetworkState()
    network.update_link("checkin-services", {"admin_up": False})
    result = network.update_link("cargo-checkin", {"admin_up": False})
    assert result["route"]["reachable"] is False
    assert network.send_request()["message"].startswith("Destination unreachable")


def test_encapsulation_mismatch_and_matching_restore():
    network = NetworkState()
    mismatch = network.update_link("checkin-services", {"encapsulation": {"R-CHECKIN": "HDLC"}})
    assert mismatch["links"]["checkin-services"]["operational"] is False
    restored = network.update_link("checkin-services", {"encapsulation": {"R-SERVICES": "HDLC"}})
    link = restored["links"]["checkin-services"]
    assert link["operational"] is True
    assert link["status_reason"] == "Operational with HDLC"


def test_cost_change_alters_route_selection():
    network = NetworkState()
    result = network.update_link("checkin-services", {"cost": 30})
    assert result["route"]["router_path"] == ["R-CHECKIN", "R-CARGO", "R-SERVICES"]
    assert result["route"]["cost"] == 20


def test_reset_restores_defaults():
    network = NetworkState()
    network.update_link("checkin-services", {"admin_up": False, "cost": 44})
    network.select_source("PC-CARGO-2")
    network.send_request()
    reset = network.reset()
    assert reset["selected_pc"] == "PC-CHECKIN-1"
    assert reset["last_request"] is None
    assert len(reset["events"]) == 1 and reset["events"][0]["type"] == "reset"
    assert all(link["admin_up"] and link["cost"] == 10 for link in reset["links"].values())
    assert all(set(link["encapsulation"].values()) == {"PPP"} for link in reset["links"].values())


def test_subnets_are_valid_non_overlapping_and_have_correct_capacities():
    assert validate_plan()
    rows = addressing_plan()
    expected = {cidr: ip_network(cidr).num_addresses - 2 for _, _, cidr in PLAN}
    assert {row["subnet"]: row["usable_capacity"] for row in rows} == expected
    for row in rows:
        assert row["usable_capacity"] >= row["required"]


@pytest.mark.parametrize("payload", [
    {"cost": 0}, {"cost": -1}, {"cost": 1.5}, {"cost": "10"}, {"cost": 10001}, {"cost": True},
    {"encapsulation": {"R-CHECKIN": "Frame Relay"}}, {"admin_up": "yes"}, {"unknown": 1},
])
def test_invalid_link_api_input(client, payload):
    response = client.patch("/api/links/checkin-services", json=payload)
    assert response.status_code == 400
    assert response.json["ok"] is False
    assert response.json["error"]["message"]


def test_invalid_ids_and_json(client):
    assert client.patch("/api/links/not-a-link", json={"cost": 10}).status_code == 400
    assert client.post("/api/route", json={"source_pc": "R-CHECKIN"}).status_code == 400
    assert client.patch("/api/links/checkin-services", data="nope", content_type="application/json").status_code == 400


def test_invalid_compound_patch_is_atomic(client):
    response = client.patch("/api/links/checkin-services", json={"admin_up": False, "cost": 0})
    assert response.status_code == 400
    current = client.get("/api/state").json["state"]["links"]["checkin-services"]
    assert current["admin_up"] is True


def test_flights_endpoint_serves_real_http_page(client):
    response = client.get("/flights")
    assert response.status_code == 200
    assert b"Flight information" in response.data
    assert b"AN 204" in response.data


def test_request_api_path_includes_all_visual_hops(client):
    response = client.post("/api/request", json={"source_pc": "PC-CHECKIN-1"})
    assert response.status_code == 200
    assert response.json["result"]["animation_path"] == [
        "PC-CHECKIN-1", "SW-CHECKIN", "R-CHECKIN", "R-SERVICES", "SW-SERVICES", "HTTP-SERVER"
    ]
