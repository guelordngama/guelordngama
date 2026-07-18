"""Tests du backend SafeCity (API, IA, géo, sécurité, validation).

Exécution :
    pytest -q
    # ou sans pytest :
    python tests/test_backend.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import create_app  # noqa: E402
from backend.ai.classifier import get_classifier  # noqa: E402
from backend.config import get_config  # noqa: E402
from backend.geo import compute_intervention, haversine_m  # noqa: E402
from backend.security import hash_password, verify_password  # noqa: E402
from backend.validation import validate_alert_payload, validate_coordinates  # noqa: E402
from backend.errors import ValidationError  # noqa: E402


def make_client():
    app = create_app(get_config("testing"))
    return app, app.test_client()


def _login(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "operateur@safecity.local", "password": "safecity123"},
    )
    return {"Authorization": "Bearer " + res.get_json()["token"]}


# --------------------------------------------------------------------------- #
# Géographie
# --------------------------------------------------------------------------- #
def test_haversine_known_distance():
    d = haversine_m(0, 0, 0, 1)
    assert 111000 < d < 112000


def test_intervention_none_when_no_patrol():
    dist, moto, walk = compute_intervention(None, None, -4.3, 15.3)
    assert dist is None and moto is None and walk is None


# --------------------------------------------------------------------------- #
# Sécurité
# --------------------------------------------------------------------------- #
def test_password_hash_roundtrip():
    h = hash_password("s3cr3t!")
    assert verify_password("s3cr3t!", h)
    assert not verify_password("mauvais", h)


def test_verify_password_handles_none():
    assert verify_password("x", None) is False


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_validate_coordinates_bounds():
    try:
        validate_coordinates(200, 15)
        assert False, "devrait lever ValidationError"
    except ValidationError:
        pass


def test_validate_alert_defaults_unknown_type():
    clean = validate_alert_payload({"type": "bidon", "lat": -4.3, "lng": 15.3})
    assert clean["type"] == "autre"


def test_validate_alert_requires_coords():
    try:
        validate_alert_payload({"type": "vol"})
        assert False
    except ValidationError:
        pass


# --------------------------------------------------------------------------- #
# IA
# --------------------------------------------------------------------------- #
def test_classifier_detects_fire():
    res = get_classifier().classify("il y a le feu et de la fumée dans la maison", "autre")
    assert res["category"] == "incendie"
    assert res["urgency"] == "critique"


def test_classifier_empty_uses_declared_type():
    res = get_classifier().classify("", "vol")
    assert res["category"] == "vol"
    assert res["engine"] == "declared"


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_health():
    _, client = make_client()
    assert client.get("/api/health").get_json()["status"] == "ok"


def test_security_headers_present():
    _, client = make_client()
    resp = client.get("/api/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_create_and_list_alert():
    _, client = make_client()
    r = client.post("/api/alerts", json={
        "type": "braquage",
        "description": "un homme armé menace la boutique",
        "lat": -4.33, "lng": 15.31,
    })
    assert r.status_code == 201
    alert = r.get_json()
    assert alert["type"] == "braquage"
    assert alert["urgency"] == "critique"
    assert alert["distance_m"] is not None
    assert alert["neighborhood"]

    alerts = client.get("/api/alerts").get_json()
    assert isinstance(alerts, list) and len(alerts) == 1


def test_list_alerts_pagination():
    _, client = make_client()
    for _ in range(3):
        client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    page = client.get("/api/alerts?page=1&page_size=2").get_json()
    assert page["total"] == 3
    assert page["page_size"] == 2
    assert len(page["items"]) == 2


def test_missing_coordinates_rejected():
    _, client = make_client()
    r = client.post("/api/alerts", json={"type": "vol"})
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "validation_error"


def test_invalid_upload_type_rejected():
    _, client = make_client()
    r = client.post("/api/alerts", json={
        "type": "vol", "lat": -4.3, "lng": 15.3,
        "photo": "data:application/x-msdownload;base64,AAAA",
    })
    assert r.status_code == 400


def test_operator_flow_requires_auth():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    assert client.post("/api/alerts/1/close").status_code == 401


def test_login_assign_and_close():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    headers = _login(client)

    assign = client.post("/api/alerts/1/assign", json={"team_id": 1}, headers=headers)
    assert assign.status_code == 200
    assert assign.get_json()["status"] == "assignee"

    close = client.post("/api/alerts/1/close", headers=headers)
    assert close.status_code == 200
    assert close.get_json()["status"] == "cloturee"


def test_assign_unknown_team_404():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    headers = _login(client)
    r = client.post("/api/alerts/1/assign", json={"team_id": 9999}, headers=headers)
    assert r.status_code == 404


def test_bad_login_rejected():
    _, client = make_client()
    r = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "mauvais",
    })
    assert r.status_code == 401


def test_stats_shape():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "incendie", "lat": -4.3, "lng": 15.3})
    stats = client.get("/api/stats").get_json()
    assert stats["total_count"] == 1
    assert "by_type" in stats and "dangerous_zones" in stats


def test_unknown_route_returns_json_404():
    _, client = make_client()
    r = client.get("/api/inexistant")
    assert r.status_code == 404
    assert "error" in r.get_json()


# --------------------------------------------------------------------------- #
# Recherche avancée / agents / analytics
# --------------------------------------------------------------------------- #
def test_search_filters():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "incendie", "lat": -4.3, "lng": 15.3,
                                     "neighborhood": "Gombe", "reporter_name": "Alice"})
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3,
                                     "neighborhood": "Limete", "reporter_name": "Bob"})
    assert client.get("/api/alerts?type=incendie").get_json()["total"] == 1
    assert client.get("/api/alerts?q=Alice").get_json()["total"] == 1
    assert client.get("/api/alerts?neighborhood=Limete").get_json()["total"] == 1
    assert client.get("/api/alerts?urgency=critique").get_json()["total"] == 1


def test_agent_accept_and_tracking():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "braquage", "lat": -4.3, "lng": 15.3})
    token = client.post("/api/auth/login", json={
        "email": "agent1@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    # position
    assert client.post("/api/agents/me/location", json={"lat": -4.31, "lng": 15.31}, headers=h).status_code == 200
    # accept
    r = client.post("/api/alerts/1/accept", headers=h)
    assert r.status_code == 200
    assert r.get_json()["assigned_agent"]["name"] == "Agent Kalala"
    assert r.get_json()["status"] == "assignee"


def test_analytics_endpoint():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    data = client.get("/api/analytics?period=month", headers=h).get_json()
    assert "agents" in data and "global_resolution_rate" in data


def test_agent_crud():
    _, client = make_client()
    token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    # create
    r = client.post("/api/agents", json={
        "name": "Agent CRUD", "email": "crud@safecity.local",
        "role": "agent", "password": "secret123"}, headers=h)
    assert r.status_code == 201
    aid = r.get_json()["id"]
    # nouvel agent peut se connecter
    assert client.post("/api/auth/login", json={
        "email": "crud@safecity.local", "password": "secret123"}).status_code == 200
    # update
    up = client.patch(f"/api/agents/{aid}", json={"name": "Agent CRUD 2"}, headers=h)
    assert up.get_json()["name"] == "Agent CRUD 2"
    # email dupliqué rejeté
    assert client.post("/api/agents", json={
        "name": "x", "email": "crud@safecity.local", "role": "agent",
        "password": "secret123"}, headers=h).status_code == 400
    # delete
    assert client.delete(f"/api/agents/{aid}", headers=h).status_code == 200


def test_agent_crud_requires_password_and_role():
    _, client = make_client()
    token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    assert client.post("/api/agents", json={"name": "z", "email": "z@x.fr", "role": "agent"},
                       headers=h).status_code == 400  # mdp manquant
    assert client.post("/api/agents", json={"name": "z", "email": "z@x.fr", "password": "secret123"},
                       headers=h).status_code == 400  # rôle manquant


def test_report_pdf():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    r = client.get("/api/reports/pdf?period=all", headers=h)
    # 200 avec reportlab, 501 sinon — les deux sont acceptables.
    assert r.status_code in (200, 501)
    if r.status_code == 200:
        assert r.data[:5] == b"%PDF-"


# --------------------------------------------------------------------------- #
# Exécution directe (sans pytest)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                failed += 1
    print(f"\n{passed} réussis, {failed} échoués")
    sys.exit(1 if failed else 0)
