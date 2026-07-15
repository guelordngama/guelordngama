"""Tests du backend SafeCity.

Exécution :
    pip install pytest
    pytest -q
    # ou sans pytest :
    python tests/test_backend.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Base de données en mémoire pour des tests isolés.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.app import create_app  # noqa: E402
from backend.ai.classifier import get_classifier  # noqa: E402
from backend.geo import compute_intervention, haversine_m  # noqa: E402


def make_client():
    app = create_app()
    app.config["TESTING"] = True
    return app, app.test_client()


# --------------------------------------------------------------------------- #
# Géographie
# --------------------------------------------------------------------------- #
def test_haversine_known_distance():
    # ~157 km entre deux points séparés d'environ 1° de longitude à l'équateur.
    d = haversine_m(0, 0, 0, 1)
    assert 111000 < d < 112000


def test_intervention_none_when_no_patrol():
    dist, moto, walk = compute_intervention(None, None, -4.3, 15.3)
    assert dist is None and moto is None and walk is None


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
    assert alert["distance_m"] is not None  # distance calculée
    assert alert["neighborhood"]

    alerts = client.get("/api/alerts").get_json()
    assert len(alerts) == 1


def test_missing_coordinates_rejected():
    _, client = make_client()
    r = client.post("/api/alerts", json={"type": "vol"})
    assert r.status_code == 400


def test_operator_flow_requires_auth():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    # Sans jeton -> refus.
    assert client.post("/api/alerts/1/close").status_code == 401


def test_login_assign_and_close():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})

    login = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123",
    })
    assert login.status_code == 200
    token = login.get_json()["token"]
    headers = {"Authorization": "Bearer " + token}

    assign = client.post("/api/alerts/1/assign", json={"team_id": 1}, headers=headers)
    assert assign.status_code == 200
    assert assign.get_json()["status"] == "assignee"

    close = client.post("/api/alerts/1/close", headers=headers)
    assert close.status_code == 200
    assert close.get_json()["status"] == "cloturee"


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
