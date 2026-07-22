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


def test_operator_assign_agent():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "braquage", "lat": -4.33, "lng": 15.31})
    op = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    ho = {"Authorization": "Bearer " + op}
    agent = [a for a in client.get("/api/agents?role=agent", headers=ho).get_json()][0]
    r = client.post("/api/alerts/1/assign-agent", json={"agent_id": agent["id"]}, headers=ho)
    assert r.status_code == 200
    assert r.get_json()["assigned_agent"]["id"] == agent["id"]
    assert r.get_json()["status"] == "assignee"
    # agent_id manquant -> 400
    assert client.post("/api/alerts/1/assign-agent", json={}, headers=ho).status_code == 400
    # réservé aux opérateurs
    ag = client.post("/api/auth/login", json={
        "email": "agent1@safecity.local", "password": "safecity123"}).get_json()["token"]
    assert client.post("/api/alerts/1/assign-agent", json={"agent_id": agent["id"]},
                       headers={"Authorization": "Bearer " + ag}).status_code == 403


def test_agent_interventions_history():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "braquage", "lat": -4.3, "lng": 15.3})
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    op = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    ag = client.post("/api/auth/login", json={
        "email": "agent1@safecity.local", "password": "safecity123"}).get_json()["token"]
    ho = {"Authorization": "Bearer " + op}
    ha = {"Authorization": "Bearer " + ag}
    agent = client.get("/api/agents?role=agent", headers=ho).get_json()[0]
    client.post("/api/alerts/1/assign-agent", json={"agent_id": agent["id"]}, headers=ho)
    client.post("/api/alerts/1/complete", headers=ha)
    client.post("/api/alerts/2/accept", headers=ha)
    # historique via opérateur
    h = client.get(f"/api/agents/{agent['id']}/interventions", headers=ho).get_json()
    assert h["total"] == 2 and h["resolved"] == 1
    assert len(h["items"]) == 2
    # historique de l'agent lui-même
    me = client.get("/api/agents/me/interventions", headers=ha).get_json()
    assert me["total"] == 2
    # endpoint opérateur interdit à un agent
    assert client.get(f"/api/agents/{agent['id']}/interventions", headers=ha).status_code == 403


def test_agent_complete_intervention():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "braquage", "lat": -4.3, "lng": 15.3})
    ag1 = client.post("/api/auth/login", json={
        "email": "agent1@safecity.local", "password": "safecity123"}).get_json()["token"]
    ag2 = client.post("/api/auth/login", json={
        "email": "agent2@safecity.local", "password": "safecity123"}).get_json()["token"]
    h1 = {"Authorization": "Bearer " + ag1}
    h2 = {"Authorization": "Bearer " + ag2}
    client.post("/api/alerts/1/accept", headers=h1)
    # un autre agent ne peut pas terminer l'intervention
    assert client.post("/api/alerts/1/complete", headers=h2).status_code == 403
    # l'agent assigné termine
    r = client.post("/api/alerts/1/complete", headers=h1)
    assert r.status_code == 200 and r.get_json()["status"] == "cloturee"
    # l'agent redevient disponible
    me = client.get("/api/agents/me", headers=h1).get_json()
    assert me["availability"] == "available" and me["current_alert_id"] is None


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


def test_messaging():
    _, client = make_client()
    op = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    ag = client.post("/api/auth/login", json={
        "email": "agent1@safecity.local", "password": "safecity123"}).get_json()["token"]
    ho = {"Authorization": "Bearer " + op}
    ha = {"Authorization": "Bearer " + ag}
    assert client.post("/api/messages", json={"text": "Intervenez Zone 5"}, headers=ho).status_code == 201
    assert client.post("/api/messages", json={"text": "Bien reçu"}, headers=ha).status_code == 201
    # message vide rejeté
    assert client.post("/api/messages", json={"text": "  "}, headers=ho).status_code == 400
    # auth requise
    assert client.get("/api/messages").status_code == 401
    msgs = client.get("/api/messages", headers=ho).get_json()
    assert len(msgs) == 2 and msgs[0]["text"] == "Intervenez Zone 5"  # ordre chronologique


def test_message_with_attachment():
    _, client = make_client()
    token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
           "AAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
    r = client.post("/api/messages", json={"text": "photo", "attachment": png}, headers=h)
    assert r.status_code == 201 and r.get_json()["attachment_url"]
    # pièce jointe seule (sans texte) acceptée
    assert client.post("/api/messages", json={"attachment": png}, headers=h).status_code == 201


def test_export_csv_and_xlsx():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "braquage", "lat": -4.3, "lng": 15.3, "reporter_name": "X"})
    token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    csv = client.get("/api/export/alerts.csv", headers=h)
    assert csv.status_code == 200 and "csv" in csv.headers["Content-Type"]
    assert b"Type" in csv.data and b"braquage" in csv.data
    xlsx = client.get("/api/export/alerts.xlsx", headers=h)
    assert xlsx.status_code in (200, 501)
    if xlsx.status_code == 200:
        assert xlsx.data[:2] == b"PK"
    assert client.get("/api/export/alerts.csv").status_code == 401


def test_notification_message_builders():
    from backend.services.notifications import _body_text, _sms_text, _subject
    alert = {
        "id": 1, "type": "braquage", "urgency": "critique", "neighborhood": "Gombe",
        "lat": -4.33, "lng": 15.31, "reporter_name": "Paul", "reporter_phone": "+243",
        "time": "16h45", "distance_m": 420, "description": "un homme armé",
    }
    assert "SafeCity" in _subject(alert) and "Braquage" in _subject(alert)
    body = _body_text(alert)
    assert "Braquage" in body and "Gombe" in body and "Paul" in body
    assert "openstreetmap.org" in body
    sms = _sms_text(alert)
    assert "Braquage" in sms and len(sms) <= 300


def test_low_urgency_alert_creation_still_works():
    # La création d'alerte ne doit jamais échouer même si les notifications
    # sont configurées (canaux non configurés en test => no-op).
    _, client = make_client()
    r = client.post("/api/alerts", json={"type": "autre", "lat": -4.3, "lng": 15.3})
    assert r.status_code == 201


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
# Inscription / connexion des citoyens
# --------------------------------------------------------------------------- #
def _register_and_verify_citizen(app, client, name, phone, password):
    """Inscrit un citoyen puis vérifie son téléphone (OTP capté via SMS simulé)."""
    from backend.services import notifications
    app.config["SMS_HTTP_URL"] = "http://sms.local/send"  # rend sms_configured() vrai
    captured = {}
    notifications.send_sms = lambda to, text: captured.update(text=text)
    r = client.post("/api/auth/register", json={
        "name": name, "phone": phone, "password": password, "consent": True})
    assert r.status_code == 201 and r.get_json()["verification_required"]
    import re as _re
    code = _re.search(r"est (\d+)\.", captured["text"]).group(1)
    v = client.post("/api/auth/verify-otp", json={"phone": phone, "code": code})
    assert v.status_code == 200
    return v.get_json()


def test_register_requires_otp_then_login_by_phone():
    app, client = make_client()
    # L'inscription n'ouvre pas de session : vérification requise.
    r = client.post("/api/auth/register", json={
        "name": "Citoyen Test", "phone": "+243 810 000 111", "password": "secret1",
        "consent": True})
    assert r.status_code == 201
    assert r.get_json().get("verification_required") is True
    assert "token" not in r.get_json()
    # Sans vérification, la connexion est refusée (phone_not_verified).
    denied = client.post("/api/auth/login", json={
        "identifier": "243810000111", "password": "secret1"})
    assert denied.status_code == 401
    assert denied.get_json()["error"]["code"] == "phone_not_verified"


def test_otp_verification_flow_and_login():
    app, client = make_client()
    body = _register_and_verify_citizen(app, client, "Citoyen", "+243810000111", "secret1")
    assert body["user"]["role"] == "citizen"
    assert body["user"]["phone_verified"] is True
    assert body["token"]
    # Connexion possible après vérification (numéro dans un autre format).
    login = client.post("/api/auth/login", json={
        "identifier": "243-810-000-111", "password": "secret1"})
    assert login.status_code == 200
    assert login.get_json()["user"]["id"] == body["user"]["id"]


def test_otp_wrong_code_rejected():
    app, client = make_client()
    app.config["SMS_HTTP_URL"] = "http://sms.local/send"
    from backend.services import notifications
    notifications.send_sms = lambda to, text: None
    client.post("/api/auth/register", json={
        "name": "C", "phone": "+243810000222", "password": "secret1", "consent": True})
    bad = client.post("/api/auth/verify-otp", json={
        "phone": "243810000222", "code": "000000"})
    assert bad.status_code == 401


def test_register_duplicate_phone_conflict():
    _, client = make_client()
    client.post("/api/auth/register", json={
        "name": "A", "phone": "+243810000111", "password": "secret1", "consent": True})
    # Même numéro sans « + » : doit être rejeté (409) avec le champ 'phone'.
    dup = client.post("/api/auth/register", json={
        "name": "B", "phone": "243810000111", "password": "secret2", "consent": True})
    assert dup.status_code == 409
    err = dup.get_json()["error"]
    assert err["code"] == "conflict"
    assert err["details"]["field"] == "phone"


def test_register_validation_errors():
    _, client = make_client()
    # Numéro manquant.
    assert client.post("/api/auth/register", json={
        "name": "X", "password": "secret1"}).status_code == 400
    # Mot de passe trop court.
    assert client.post("/api/auth/register", json={
        "name": "X", "phone": "+243810000222", "password": "123"}).status_code == 400


def test_register_requires_consent():
    _, client = make_client()
    # Sans consentement à la politique de confidentialité → refus.
    r = client.post("/api/auth/register", json={
        "name": "X", "phone": "+243810000444", "password": "secret1"})
    assert r.status_code == 400
    assert "confidentialité" in r.get_json()["error"]["message"]


def test_delete_own_account_anonymises_alerts():
    app, client = make_client()
    body = _register_and_verify_citizen(app, client, "Citoyen", "+243810000111", "secret1")
    uid = body["user"]["id"]
    token = body["token"]
    # Une alerte rattachée au citoyen.
    client.post("/api/alerts", json={
        "type": "vol", "lat": -4.3, "lng": 15.3,
        "reporter_id": uid, "reporter_name": "Citoyen", "reporter_phone": "+243810000111"})
    # Suppression du compte (droit à l'effacement).
    h = {"Authorization": "Bearer " + token}
    assert client.delete("/api/auth/me", headers=h).status_code == 200
    # Le compte n'existe plus (reconnexion impossible).
    assert client.post("/api/auth/login", json={
        "identifier": "243810000111", "password": "secret1"}).status_code == 401
    # L'alerte subsiste mais est anonymisée.
    from backend.models import Alert
    with app.app_context():
        a = Alert.query.first()
        assert a is not None
        assert a.reporter_id is None
        assert a.reporter_phone is None
        assert "supprimé" in a.reporter_name


def test_purge_old_alerts():
    from datetime import datetime, timedelta

    from backend.models import Alert
    from backend.services.retention import purge_old_alerts
    app, client = make_client()
    client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    with app.app_context():
        a = Alert.query.first()
        a.status = "cloturee"
        a.closed_at = datetime.utcnow() - timedelta(days=400)
        from backend.extensions import db
        db.session.commit()
        assert purge_old_alerts(365) == 1
        assert Alert.query.count() == 0


def test_login_wrong_password_is_generic():
    _, client = make_client()
    client.post("/api/auth/register", json={
        "name": "C", "phone": "+243810000333", "password": "secret1", "consent": True})
    bad = client.post("/api/auth/login", json={
        "identifier": "243810000333", "password": "faux"})
    assert bad.status_code == 401


def test_register_staff_creates_operator():
    app, client = make_client()
    app.config["STAFF_INVITE_CODE"] = "CODE"
    r = client.post("/api/auth/register-staff", json={
        "name": "Georges", "email": "georges@safecity.local", "password": "secret1",
        "invite_code": "CODE"})
    assert r.status_code == 201
    assert r.get_json()["user"]["role"] == "operator"
    # L'opérateur peut se connecter par e-mail.
    login = client.post("/api/auth/login", json={
        "email": "georges@safecity.local", "password": "secret1"})
    assert login.status_code == 200


def test_register_staff_duplicate_email_conflict():
    app, client = make_client()
    app.config["STAFF_INVITE_CODE"] = "CODE"
    client.post("/api/auth/register-staff", json={
        "name": "A", "email": "dup@safecity.local", "password": "secret1", "invite_code": "CODE"})
    dup = client.post("/api/auth/register-staff", json={
        "name": "B", "email": "dup@safecity.local", "password": "secret2", "invite_code": "CODE"})
    assert dup.status_code == 409
    assert dup.get_json()["error"]["details"]["field"] == "email"


def test_staff_signup_disabled_without_invite_code():
    # Par défaut (aucun code configuré), l'auto-inscription est désactivée.
    app, client = make_client()
    assert not app.config["STAFF_INVITE_CODE"]
    r = client.post("/api/auth/register-staff", json={
        "name": "G", "email": "g@x.com", "password": "secret1"})
    assert r.status_code == 403


def test_staff_signup_requires_valid_invite_code():
    app, client = make_client()
    app.config["STAFF_INVITE_CODE"] = "MAIRIE2026"
    bad = client.post("/api/auth/register-staff", json={
        "name": "G", "email": "g@x.com", "password": "secret1", "invite_code": "X"})
    assert bad.status_code == 403
    ok = client.post("/api/auth/register-staff", json={
        "name": "G", "email": "g@x.com", "password": "secret1", "invite_code": "MAIRIE2026"})
    assert ok.status_code == 201


def test_change_password_flow():
    app, client = make_client()
    app.config["STAFF_INVITE_CODE"] = "CODE"
    client.post("/api/auth/register-staff", json={
        "name": "G", "email": "g@x.com", "password": "secret1", "invite_code": "CODE"})
    token = client.post("/api/auth/login", json={
        "email": "g@x.com", "password": "secret1"}).get_json()["token"]
    h = {"Authorization": "Bearer " + token}
    # Mauvais mot de passe actuel → 401.
    assert client.post("/api/auth/change-password", json={
        "current_password": "faux", "new_password": "nouveau1"}, headers=h).status_code == 401
    # Correct → 200, l'ancien ne marche plus, le nouveau oui.
    assert client.post("/api/auth/change-password", json={
        "current_password": "secret1", "new_password": "nouveau1"}, headers=h).status_code == 200
    assert client.post("/api/auth/login", json={
        "email": "g@x.com", "password": "secret1"}).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "g@x.com", "password": "nouveau1"}).status_code == 200
    # Sans authentification → 401.
    assert client.post("/api/auth/change-password", json={
        "current_password": "x", "new_password": "yyyyyy"}).status_code == 401


def test_audit_log_records_and_is_admin_only():
    _, client = make_client()
    # Génère des événements audités.
    client.post("/api/auth/login", json={"email": "x@x.com", "password": "faux"})  # login_failed
    client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"})           # login

    # Un admin peut consulter le journal.
    admin_tok = client.post("/api/auth/login", json={
        "email": "admin@safecity.local", "password": "safecity123"}).get_json()["token"]
    ah = {"Authorization": "Bearer " + admin_tok}
    r = client.get("/api/audit", headers=ah)
    assert r.status_code == 200
    actions = {e["action"] for e in r.get_json()}
    assert "login_failed" in actions and "login" in actions

    # Un opérateur ne peut pas consulter le journal ; anonyme non plus.
    op_tok = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    assert client.get("/api/audit", headers={"Authorization": "Bearer " + op_tok}).status_code == 403
    assert client.get("/api/audit").status_code == 401


def test_forgot_password_without_smtp_returns_503():
    # En test, aucun SMTP n'est configuré : la réinitialisation par e-mail est
    # indisponible et renvoie un message clair (code email_not_configured).
    _, client = make_client()
    client.post("/api/auth/register-staff", json={
        "name": "C", "email": "c@safecity.local", "password": "secret1"})
    r = client.post("/api/auth/forgot-password", json={"email": "c@safecity.local"})
    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "email_not_configured"


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
