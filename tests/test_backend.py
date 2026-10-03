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


_STAFF_TOKENS = {}


def _staff(client):
    """En-têtes d'un opérateur connecté (mis en cache par client de test)."""
    key = id(client)
    if key not in _STAFF_TOKENS:
        _STAFF_TOKENS[key] = _login(client)
    return _STAFF_TOKENS[key]


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


def test_tile_proxy_rejects_out_of_bounds():
    # Le proxy de tuiles refuse les coordonnées hors bornes (z/x/y) sans jamais
    # solliciter le réseau : indices absurdes → 400.
    _, client = make_client()
    assert client.get("/tiles/30/1/1.png").status_code == 400  # z > 20
    assert client.get("/tiles/1/9/0.png").status_code == 400   # x hors plage


def test_tile_proxy_uses_osm_then_backup_provider():
    """Fond OpenStreetMap (CARTO exige une clé : « API KEY REQUIRED ») ; si OSM
    échoue, le fournisseur de secours est utilisé. Route versionnée /tiles/v2/."""
    import tempfile
    import backend.api.tiles as tiles

    tiles._fail_count = 0
    tiles._cooldown_until = 0.0
    original = tiles.urllib.request.urlopen
    asked = []

    class _Resp:
        headers = {"Content-Type": "image/png"}

        def __init__(self, data):
            self._d = data

        def read(self):
            return self._d

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake(req, timeout=None):
        asked.append(req.full_url)
        assert "SafeCity" in req.get_header("User-agent")
        if "openstreetmap" in req.full_url:
            raise TimeoutError("osm down")
        return _Resp(b"\x89PNG\r\n\x1a\n" + b"E" * 200)

    tiles.urllib.request.urlopen = _fake
    try:
        app, client = make_client()
        root = tempfile.mkdtemp()
        app.config["TILECACHE_DIR"] = root
        open(os.path.join(root, "5_1_1.png"), "wb").write(b"ancienne tuile CARTO")
        tiles._purged = False
        r = client.get("/tiles/v2/12/2361/2208.png")
        assert r.status_code == 200 and r.data.endswith(b"E" * 50)
        assert "tile.openstreetmap.org/12/2361/2208.png" in asked[0]
        assert "arcgisonline" in asked[1] and asked[1].endswith("/12/2208/2361")
        assert not any("carto" in u for u in asked)
        assert not os.path.exists(os.path.join(root, "5_1_1.png"))   # ancien cache purgé
        n = len(asked)
        assert client.get("/tiles/12/2361/2208.png").status_code == 200  # ancienne route
        assert len(asked) == n                                             # servi du cache
    finally:
        tiles.urllib.request.urlopen = original
        tiles._fail_count = 0
        tiles._cooldown_until = 0.0


def test_tile_proxy_serves_neutral_fallback_when_cdn_down():
    # Quand le serveur ne peut pas joindre le CDN de tuiles, le proxy renvoie un
    # fond neutre PNG (200) au lieu d'une erreur 502, sans bloquer.
    import backend.api.tiles as tiles

    tiles._fail_count = 0
    tiles._cooldown_until = 0.0
    original = tiles.urllib.request.urlopen

    def _boom(*a, **k):
        raise TimeoutError("timed out")

    tiles.urllib.request.urlopen = _boom
    try:
        _, client = make_client()
        r = client.get("/tiles/16/44823/33836.png")
        assert r.status_code == 200
        assert r.mimetype == "image/png"
        assert r.data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG valide
        assert "max-age=30" in r.headers.get("Cache-Control", "")  # cache court
    finally:
        tiles.urllib.request.urlopen = original
        tiles._fail_count = 0
        tiles._cooldown_until = 0.0


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
    # L'adresse contient toujours la position exacte (les coordonnées GPS), même
    # sans géocodage : c'est le localisateur fiable. Le quartier réel est ajouté
    # ensuite par géocodage (désactivé pendant les tests → None ici, pas de faux).
    assert alert["address"]
    assert "°" in alert["address"]

    alerts = client.get("/api/alerts", headers=_staff(client)).get_json()
    assert isinstance(alerts, list) and len(alerts) == 1


def test_alert_location_details_and_accuracy():
    """Fiche d'alerte détaillée : ville, précision GPS, placement manuel,
    et analyse des champs OpenStreetMap (commune / quartier / avenue)."""
    from backend.geo import parse_osm_address
    _, client = make_client()
    # Vraie position GPS à Lubumbashi, précision annoncée par le téléphone.
    a = client.post("/api/alerts", json={
        "type": "braquage", "description": "braquage", "lat": -11.6876,
        "lng": 27.5026, "accuracy": 8.4}).get_json()
    assert a["gps_accuracy_m"] == 8
    assert a["city"] == "Lubumbashi"
    assert a["position_manual"] is False
    for k in ("street", "commune", "neighborhood"):
        assert k in a                 # champs présents (remplis par géocodage)
    # Placement manuel : pas de précision GPS (elle serait fausse).
    m = client.post("/api/alerts", json={
        "type": "vol", "description": "vol", "lat": -11.66, "lng": 27.48,
        "accuracy": 12, "position_manual": True}).get_json()
    assert m["position_manual"] is True and m["gps_accuracy_m"] is None
    # Précision absurde ignorée ; hors agglomération → ville inconnue.
    x = client.post("/api/alerts", json={
        "type": "vol", "description": "vol", "lat": -4.33, "lng": 15.31,
        "accuracy": -3}).get_json()
    assert x["gps_accuracy_m"] is None and x["city"] is None
    # Position approximative : ni précision ni ville.
    ap = client.post("/api/alerts", json={
        "type": "vol", "description": "vol", "lat": -11.66, "lng": 27.48,
        "accuracy": 8, "position_approx": True}).get_json()
    assert ap["gps_accuracy_m"] is None and ap["city"] is None

    # Heure affichée = heure LOCALE de Lubumbashi (UTC+2), pas l'UTC stocké.
    from datetime import datetime, timedelta
    utc = datetime.fromisoformat(a["created_at"].replace("Z", ""))
    assert a["time"] == (utc + timedelta(hours=2)).strftime("%H:%M")
    assert a["created_local"] == (utc + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

    d = parse_osm_address({"road": "Avenue Kasai", "neighbourhood": "Makutano",
                           "city_district": "Lubumbashi", "city": "Lubumbashi"})
    assert d == {"street": "Avenue Kasai", "neighborhood": "Makutano",
                 "commune": "Lubumbashi", "city": "Lubumbashi"}
    d = parse_osm_address({"road": "Rue Mitwaba", "suburb": "Kenya",
                           "quarter": "Bongonga"}, -11.69, 27.50)
    assert d["commune"] == "Kenya" and d["neighborhood"] == "Bongonga"
    assert d["city"] == "Lubumbashi"


def test_parse_osm_address_lubumbashi_field_mapping():
    """Cas réel signalé : un champ Nominatim contient une avenue/rue au lieu
    d'un vrai quartier (« suburb » : « Avenue Kapanga »), et le champ « city »
    retombe sur la province voisine (« Lualaba ») faute de limite communale
    précise dans OpenStreetMap à cet endroit. Le quartier ne doit jamais être
    une avenue/rue, et la ville doit rester Lubumbashi dans l'agglomération."""
    from backend.geo import parse_osm_address

    addr = {
        "road": "Avenue de la Digue",
        "suburb": "Avenue Kapanga",       # piège : ressemble à une avenue
        "residential": "Luapula",          # le vrai quartier, plus loin dans l'ordre
        "city_district": "Kenya",
        "city": "Lualaba",                 # piège : une province, pas la ville
        "country": "République démocratique du Congo",
    }
    d = parse_osm_address(addr, lat=-11.705024, lng=27.485672)
    assert d["street"] == "Avenue de la Digue"
    assert d["commune"] == "Kenya"
    assert d["neighborhood"] == "Luapula"          # jamais « Avenue Kapanga »
    assert d["city"] == "Lubumbashi"               # jamais « Lualaba »

    # Hors de l'agglomération de Lubumbashi : la ville reste dynamique, prise
    # telle quelle chez le service (jamais Lubumbashi imposée ailleurs).
    far = parse_osm_address({"city": "Kolwezi", "suburb": "Manika"}, lat=-10.72, lng=25.47)
    assert far["city"] == "Kolwezi" and far["neighborhood"] == "Manika"

    # Si tout est écarté (rien d'exploitable), le quartier reste vide —
    # jamais un quartier inventé.
    only_streets = parse_osm_address({"suburb": "Avenue X", "residential": "Rue Y"},
                                     lat=-11.66, lng=27.48)
    assert only_streets["neighborhood"] is None


def test_geo_reverse_endpoint():
    """Adresse d'une position pour l'app citoyenne (service OSM simulé)."""
    import backend.api.geo as geo_api
    app, client = make_client()
    # Géocodage désactivé (tests) : pas d'adresse inventée, ville déduite.
    r = client.get("/api/geo/reverse?lat=-11.6876&lng=27.5026")
    assert r.status_code == 200
    d = r.get_json()
    assert d["available"] is False and d["city"] == "Lubumbashi" and d["commune"] is None
    assert client.get("/api/geo/reverse?lat=abc&lng=27").status_code == 400
    assert client.get("/api/geo/reverse?lat=-95&lng=27").status_code == 400
    # Service disponible : on renvoie les champs détaillés.
    app.config["GEOCODING_ENABLED"] = True
    orig = geo_api.reverse_geocode_details
    geo_api.reverse_geocode_details = lambda lat, lng: {
        "street": "Avenue Sendwe", "neighborhood": "Bongonga", "commune": "Kenya",
        "city": "Lubumbashi", "address": "x"}
    try:
        d = client.get("/api/geo/reverse?lat=-11.6876&lng=27.5026").get_json()
    finally:
        geo_api.reverse_geocode_details = orig
    assert d == {"available": True, "street": "Avenue Sendwe", "neighborhood": "Bongonga",
                 "commune": "Kenya", "city": "Lubumbashi"}


def test_geo_route_endpoint():
    """Itinéraire agent -> alerte calculé par le serveur (repli ligne droite)."""
    _, client = make_client()
    q = "/api/geo/route?from=-11.6647,27.4794&to=-11.6876,27.5026"
    assert client.get(q).status_code == 401            # personnel uniquement
    h = _login(client)
    d = client.get(q, headers=h).get_json()
    assert d["source"] == "direct" and len(d["coordinates"]) == 2
    assert 3000 < d["distance_m"] < 6000 and d["duration_s"] > 0
    assert client.get("/api/geo/route?from=abc&to=1,2", headers=h).status_code == 400


def test_agent_positions_for_portal_map():
    """Carte du portail : positions des collègues, sans données personnelles."""
    _, client = make_client()
    assert client.get("/api/agents/positions").status_code == 401
    tok = client.post("/api/auth/login", json={"email": "agent1@safecity.local",
                                                "password": "safecity123"}).get_json()["token"]
    h = {"Authorization": "Bearer " + tok}
    client.post("/api/agents/me/location", json={"lat": -11.66, "lng": 27.48}, headers=h)
    r = client.get("/api/agents/positions", headers=h)
    assert r.status_code == 200
    items = r.get_json()
    assert items and all(i["role"] == "agent" for i in items)
    me = [i for i in items if i["lat"] is not None][0]
    assert abs(me["lat"] + 11.66) < 1e-6
    for i in items:
        assert "email" not in i and "phone" not in i and "permissions" not in i


def test_security_personal_data_requires_staff():
    """Fuite corrigée : alertes (nom, téléphone, GPS des citoyens), patrouilles et
    statistiques ne sont plus lisibles sans compte du personnel."""
    from types import SimpleNamespace
    from backend.security import generate_token
    app, client = make_client()
    a = client.post("/api/alerts", json={"type": "vol", "description": "vol",
                    "lat": -11.66, "lng": 27.48, "reporter_name": "Jean",
                    "reporter_phone": "+243812345678"}).get_json()
    for url in ("/api/alerts", f"/api/alerts/{a['id']}", "/api/stats", "/api/teams"):
        assert client.get(url).status_code == 401, url
    with app.app_context():
        citizen = generate_token(SimpleNamespace(id=999, role="citizen", email="c@x", name="C"))
    hc = {"Authorization": "Bearer " + citizen}
    for url in ("/api/alerts", f"/api/alerts/{a['id']}", "/api/stats", "/api/teams"):
        assert client.get(url, headers=hc).status_code == 403, url
    h = _login(client)
    for url in ("/api/alerts", f"/api/alerts/{a['id']}", "/api/stats", "/api/teams"):
        assert client.get(url, headers=h).status_code == 200, url
    # Le citoyen suit toujours SON alerte par référence (sans données personnelles).
    t = client.get("/api/alerts/track/" + a["reference"]).get_json()
    assert "reporter_phone" not in t and "lat" not in t


def test_security_realtime_only_for_staff():
    """Temps réel : seul le personnel authentifié reçoit alertes / agents / messages."""
    from types import SimpleNamespace
    from backend import socketio
    from backend.realtime import online_user_ids
    from backend.security import generate_token
    app, client = make_client()
    op_token = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    with app.app_context():
        citizen = generate_token(SimpleNamespace(id=999, role="citizen", email="c@x", name="C"))
    anon = socketio.test_client(app)
    cit = socketio.test_client(app, auth={"token": citizen})
    forged = socketio.test_client(app, auth={"token": op_token[:-4] + "abcd"})
    staff = socketio.test_client(app, auth={"token": op_token})
    for c in (anon, cit, forged, staff):
        assert c.is_connected()
    first = anon.get_received()
    assert [e["args"][0]["authorized"] for e in first if e["name"] == "connected"] == [False]
    cit.get_received(); forged.get_received(); staff.get_received()
    # Usurpation de présence : un anonyme se déclare « utilisateur 1 ».
    anon.emit("identify", {"uid": 1})
    assert 1 not in online_user_ids()
    client.post("/api/alerts", json={"type": "vol", "description": "vol", "lat": -11.66,
                                     "lng": 27.48, "reporter_phone": "+243812345678"})
    for c, name in ((anon, "anonyme"), (cit, "citoyen"), (forged, "jeton falsifié")):
        assert c.get_received() == [], name + " ne doit rien recevoir"
    got = [e["name"] for e in staff.get_received()]
    assert "new_alert" in got
    for c in (anon, cit, forged, staff):
        c.disconnect()


def test_security_uploads_signed_links():
    """Photos / vocaux / vidéos : lien signé et expirant obligatoire."""
    import base64, time
    from types import SimpleNamespace
    from backend.security import generate_token, _upload_sig
    app, client = make_client()
    img = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode()
    a = client.post("/api/alerts", json={"type": "vol", "description": "vol", "lat": -11.66,
                                         "lng": 27.48, "photo": img}).get_json()
    url = a["photo_url"]
    path, query = url.split("?")
    fname = path.rsplit("/", 1)[1]
    assert "exp=" in query and "sig=" in query
    assert client.get(url).status_code == 200                       # lien signé valide
    r = client.get(url)
    assert "private" in r.headers.get("Cache-Control", "")
    assert client.get(path).status_code == 403                      # sans signature
    assert client.get(path + "?exp=9999999999&sig=AAAA").status_code == 403   # falsifié
    exp = query.split("exp=")[1].split("&")[0]
    sig = query.split("sig=")[1]
    other = client.post("/api/alerts", json={"type": "vol", "description": "vol", "lat": -11.66,
                                             "lng": 27.48, "photo": img}).get_json()["photo_url"]
    other_path = other.split("?")[0]
    assert client.get(f"{other_path}?exp={exp}&sig={sig}").status_code == 403   # autre fichier
    with app.app_context():
        old = int(time.time()) - 10
        expired = f"{path}?exp={old}&sig={_upload_sig(fname, old)}"
    assert client.get(expired).status_code == 403                   # expiré
    assert client.get(f"{path}?exp={int(exp) + 3600}&sig={sig}").status_code == 403  # exp modifiée
    assert client.get("/uploads/../config.py?exp=9999999999&sig=x").status_code in (403, 404)
    # Personnel : accès aussi par en-tête (outils internes) ; citoyen : refusé.
    assert client.get(path, headers=_login(client)).status_code == 200
    with app.app_context():
        cit = generate_token(SimpleNamespace(id=999, role="citizen", email="c@x", name="C"))
    assert client.get(path, headers={"Authorization": "Bearer " + cit}).status_code == 403


def test_incident_numbers_history_and_assignment():
    """N° d'intervention SC-AAAA-NNNN séquentiel, recherche, agent affecté avec
    position et statut (affichage « Agent X → Intervention #… »)."""
    from datetime import datetime, timedelta
    app, client = make_client()
    h = _staff(client)
    year = (datetime.utcnow() + timedelta(hours=2)).year
    nums = []
    for t in ("braquage", "accident", "incendie"):
        a = client.post("/api/alerts", json={"type": t, "description": t, "lat": -11.66 - len(nums),
                                             "lng": 27.48}).get_json()
        nums.append(a["incident_number"])
    assert nums == [f"SC-{year}-0001", f"SC-{year}-0002", f"SC-{year}-0003"]
    # Le code citoyen reste aléatoire et distinct du numéro interne.
    assert a["reference"] != a["incident_number"] and not a["reference"].startswith(f"SC-{year}")
    # Recherche par numéro (historique).
    r = client.get(f"/api/alerts?q=SC-{year}-0002&page=1&page_size=10", headers=h).get_json()
    assert r["total"] == 1 and r["items"][0]["type"] == "accident"
    # Affectation : l'alerte porte la position et le statut de l'agent.
    agents = client.get("/api/agents", headers=h).get_json()
    ag = [x for x in agents if x["role"] == "agent"][0]
    tok = client.post("/api/auth/login", json={"email": ag["email"], "password": "safecity123"}).get_json()["token"]
    client.post("/api/agents/me/location", json={"lat": -11.67, "lng": 27.49},
                headers={"Authorization": "Bearer " + tok})
    alert_id = r["items"][0]["id"]
    up = client.post(f"/api/alerts/{alert_id}/assign-agent", json={"agent_id": ag["id"]}, headers=h).get_json()
    aa = up["assigned_agent"]
    assert aa["name"] == ag["name"] and aa["lat"] == -11.67 and aa["availability"] == "busy"
    assert up["status"] == "assignee" and up["incident_number"] == f"SC-{year}-0002"
    # Deux alertes au même instant : le numéro déjà pris est détecté, on réessaie.
    import backend.services.alerts as svc
    real, calls = svc._next_incident_number, {"n": 0}
    def colliding():
        calls["n"] += 1
        return f"SC-{year}-0001" if calls["n"] <= 2 else real()
    svc._next_incident_number = colliding
    try:
        d = client.post("/api/alerts", json={"type": "vol", "description": "v", "lat": -11.7,
                                             "lng": 27.5}).get_json()
    finally:
        svc._next_incident_number = real
    assert d["incident_number"] == f"SC-{year}-0004" and calls["n"] == 3


def test_citizen_track_alert_by_reference():
    _, client = make_client()
    r = client.post("/api/alerts", json={
        "type": "vol", "description": "un vol au marché", "lat": -4.33, "lng": 15.31,
    })
    ref = r.get_json()["reference"]
    assert ref and ref.startswith("SC-")

    # Suivi public : avancement seulement, aucune donnée sensible.
    t = client.get("/api/alerts/track/" + ref)
    assert t.status_code == 200
    d = t.get_json()
    assert d["status"] == "active"
    assert d["stage"] == "received"
    assert [s["key"] for s in d["steps"]] == [
        "new", "received", "assigned", "en_route", "on_site", "resolved"]
    # Nouvelle/Reçue acquises dès la création ; le reste suit la progression réelle.
    assert d["steps"][0]["done"] is True and d["steps"][1]["done"] is True
    assert all(s["done"] is False for s in d["steps"][2:])
    for leaked in ("reporter_phone", "reporter_name", "description", "lat", "lng"):
        assert leaked not in d, f"donnée sensible exposée : {leaked}"

    # Référence inconnue → 404 ; casse insensible.
    assert client.get("/api/alerts/track/SC-ZZZZZZ").status_code == 404
    assert client.get("/api/alerts/track/" + ref.lower()).status_code == 200


def test_citizen_alert_accepts_video():
    import base64
    _, client = make_client()
    vid = "data:video/mp4;base64," + base64.b64encode(b"FAKEMP4DATA0123456789").decode()
    r = client.post("/api/alerts", json={
        "type": "accident", "description": "accident filmé",
        "lat": -4.33, "lng": 15.31, "video": vid,
    })
    assert r.status_code == 201
    d = r.get_json()
    assert d["video_url"] and d["video_url"].split("?")[0].endswith(".mp4")
    # Le fichier est bien servi.
    assert client.get(d["video_url"]).status_code == 200


def test_duplicate_alerts_are_grouped():
    app, client = make_client()
    app.config["DEDUP_ENABLED"] = True
    app.config["DEDUP_RADIUS_M"] = 150
    app.config["DEDUP_WINDOW_MIN"] = 10

    def post(t, lat, lng):
        return client.post("/api/alerts", json={
            "type": t, "description": "incident " + t, "lat": lat, "lng": lng,
        }).get_json()

    a1 = post("incendie", -11.6600, 27.4800)          # principal
    a2 = post("incendie", -11.6604, 27.4802)          # même incendie, ~50 m
    a3 = post("vol", -11.6600, 27.4800)               # même lieu, type différent
    a4 = post("incendie", -11.7500, 27.6000)          # incendie loin (~20 km)

    assert a1["duplicate_of"] is None
    assert a2["duplicate_of"] == a1["id"], "doublon rattaché au principal"
    assert a3["duplicate_of"] is None, "type différent : pas un doublon"
    assert a4["duplicate_of"] is None, "trop loin : pas un doublon"

    # La liste opérateur ne montre que les incidents principaux (doublon masqué).
    alerts = client.get("/api/alerts", headers=_staff(client)).get_json()
    ids = {a["id"] for a in alerts}
    assert a2["id"] not in ids and a1["id"] in ids
    primary = next(a for a in alerts if a["id"] == a1["id"])
    assert primary["duplicate_count"] == 1


def test_list_alerts_pagination():
    _, client = make_client()
    for _ in range(3):
        client.post("/api/alerts", json={"type": "vol", "lat": -4.3, "lng": 15.3})
    page = client.get("/api/alerts?page=1&page_size=2", headers=_staff(client)).get_json()
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
    stats = client.get("/api/stats", headers=_staff(client)).get_json()
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
    assert client.get("/api/alerts?type=incendie", headers=_staff(client)).get_json()["total"] == 1
    assert client.get("/api/alerts?q=Alice", headers=_staff(client)).get_json()["total"] == 1
    assert client.get("/api/alerts?neighborhood=Limete", headers=_staff(client)).get_json()["total"] == 1
    assert client.get("/api/alerts?urgency=critique", headers=_staff(client)).get_json()["total"] == 1


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


def test_progress_stages_full_cycle():
    """Progression Nouvelle → Reçue → Assignée → Agent en route → Sur place →
    Résolue : chaque étape passe à `done` au bon moment, sans toucher `status`
    (qui continue de piloter le reste de l'application)."""
    _, client = make_client()
    a = client.post("/api/alerts", json={"type": "incendie", "lat": -11.66, "lng": 27.48}).get_json()
    aid, ref = a["id"], a["reference"]
    assert a["stage"] == "received"

    op = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    ho = {"Authorization": "Bearer " + op}
    ag = client.post("/api/auth/login", json={
        "email": "agent1@safecity.local", "password": "safecity123"}).get_json()["token"]
    ha = {"Authorization": "Bearer " + ag}

    def steps_by_key(ref):
        return {s["key"]: s["done"] for s in client.get("/api/alerts/track/" + ref).get_json()["steps"]}

    agent = client.get("/api/agents?role=agent", headers=ho).get_json()[0]
    r = client.post(f"/api/alerts/{aid}/assign-agent", json={"agent_id": agent["id"]}, headers=ho)
    assert r.get_json()["stage"] == "assigned"
    st = steps_by_key(ref)
    assert st["assigned"] is True and st["en_route"] is False

    # Un agent d'un autre compte ne peut pas signaler l'arrivée à sa place.
    other = client.post("/api/auth/login", json={
        "email": "agent2@safecity.local", "password": "safecity123"}).get_json()["token"]
    ho2 = {"Authorization": "Bearer " + other}
    assert client.post(f"/api/alerts/{aid}/arrived", headers=ho2).status_code == 403

    r = client.post(f"/api/alerts/{aid}/accept", headers=ha)
    assert r.get_json()["stage"] == "en_route"
    assert steps_by_key(ref)["en_route"] is True and steps_by_key(ref)["on_site"] is False

    r = client.post(f"/api/alerts/{aid}/arrived", headers=ha)
    assert r.status_code == 200 and r.get_json()["stage"] == "on_site"
    assert r.get_json()["arrived_at"]
    assert steps_by_key(ref)["on_site"] is True and steps_by_key(ref)["resolved"] is False

    r = client.post(f"/api/alerts/{aid}/complete", headers=ha)
    assert r.get_json()["stage"] == "resolved" and r.get_json()["status"] == "cloturee"
    final = steps_by_key(ref)
    assert all(final.values())

    # Le centre peut aussi signaler l'arrivée pour le compte d'un agent (radio).
    b = client.post("/api/alerts", json={"type": "vol", "lat": -11.66, "lng": 27.48}).get_json()
    client.post(f"/api/alerts/{b['id']}/assign-agent", json={"agent_id": agent["id"]}, headers=ho)
    r2 = client.post(f"/api/alerts/{b['id']}/arrived", headers=ho)
    assert r2.status_code == 200 and r2.get_json()["stage"] == "on_site"

    # Journalisé (visible au superviseur).
    hs = {"Authorization": "Bearer " + client.post('/api/auth/login', json={
        'email': 'superviseur@safecity.local', 'password': 'safecity123'}).get_json()['token']}
    journal = client.get(f"/api/alerts/{aid}/journal", headers=hs).get_json()
    assert "agent_arrived" in [e["action"] for e in journal]


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
    """Inscrit un citoyen : le compte est activé immédiatement (sans code)."""
    r = client.post("/api/auth/register", json={
        "name": name, "phone": phone, "password": password, "consent": True})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body.get("token") and body["user"]["phone_verified"] is True
    return body


def test_register_activates_and_login_directly():
    app, client = make_client()
    # L'inscription active le compte et connecte directement (jeton renvoyé).
    r = client.post("/api/auth/register", json={
        "name": "Citoyen Test", "phone": "+243 810 000 111", "password": "secret1",
        "consent": True})
    assert r.status_code == 201
    assert r.get_json().get("token")
    assert r.get_json()["user"]["phone_verified"] is True
    # Connexion possible immédiatement (numéro dans un autre format).
    login = client.post("/api/auth/login", json={
        "identifier": "243-810-000-111", "password": "secret1"})
    assert login.status_code == 200
    assert login.get_json()["user"]["role"] == "citizen"


def test_register_duplicate_phone_conflict():
    app, client = make_client()
    app.config["SMS_HTTP_URL"] = "http://sms.local/send"  # SMS configuré → e-mail non requis
    from backend.services import notifications
    notifications.send_sms = lambda to, text: None
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


def test_password_reset_by_sms():
    app, client = make_client()
    _register_and_verify_citizen(app, client, "Citoyen", "+243810000111", "ancien1")
    import re as _re

    from backend.services import notifications
    app.config["SMS_HTTP_URL"] = "http://sms.local/send"  # passerelle SMS active
    captured = {}
    notifications.send_sms = lambda to, text: captured.update(text=text)
    assert client.post("/api/auth/forgot-password-sms", json={
        "phone": "243810000111"}).status_code == 200
    code = _re.search(r"est (\d+)\.", captured["text"]).group(1)
    # Mauvais code → 401.
    assert client.post("/api/auth/reset-password-sms", json={
        "phone": "243810000111", "code": "000000", "new_password": "nouveau1"}).status_code == 401
    # Bon code → 200, l'ancien mot de passe ne marche plus.
    ok = client.post("/api/auth/reset-password-sms", json={
        "phone": "243810000111", "code": code, "new_password": "nouveau1"})
    assert ok.status_code == 200 and ok.get_json()["token"]
    assert client.post("/api/auth/login", json={
        "identifier": "243810000111", "password": "ancien1"}).status_code == 401
    assert client.post("/api/auth/login", json={
        "identifier": "243810000111", "password": "nouveau1"}).status_code == 200


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


_TEST_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
             "AAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")


def test_profile_avatar_citizen_and_staff():
    """Photo de profil : citoyen et personnel peuvent définir/retirer la leur ;
    l'ancien fichier est supprimé (pas de fichiers orphelins) ; visible dans
    les listes agents/citoyens (poste opérateur)."""
    import os

    app, client = make_client()
    # Citoyen (inscription directe, activée, jeton renvoyé immédiatement).
    reg = client.post("/api/auth/register", json={
        "name": "Awa", "phone": "+243899000111", "password": "secret1", "consent": True})
    assert reg.status_code == 201, reg.get_json()
    ctok = reg.get_json()["token"]
    hc = {"Authorization": "Bearer " + ctok}

    # Sans authentification → 401.
    assert client.post("/api/auth/me/avatar", json={"photo": _TEST_PNG}).status_code == 401
    # Champ manquant → 400.
    assert client.post("/api/auth/me/avatar", json={}, headers=hc).status_code == 400

    r = client.post("/api/auth/me/avatar", json={"photo": _TEST_PNG}, headers=hc)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["avatar_url"] and d["avatar_url"].startswith("/uploads/")
    old_filename = d["avatar_url"].split("/uploads/")[1].split("?")[0]
    old_path = os.path.join(app.config["UPLOAD_DIR"], old_filename)
    assert os.path.exists(old_path)

    # Remplacement : l'ancien fichier disparaît, un nouveau lien est renvoyé.
    r2 = client.post("/api/auth/me/avatar", json={"photo": _TEST_PNG}, headers=hc)
    assert r2.status_code == 200
    assert not os.path.exists(old_path)

    # Lien signé valable (comme les photos d'alerte).
    assert client.get(r2.get_json()["avatar_url"]).status_code == 200

    # Suppression.
    r3 = client.delete("/api/auth/me/avatar", headers=hc)
    assert r3.status_code == 200 and r3.get_json()["avatar_url"] is None

    # Personnel (opérateur) : même mécanisme, visible dans /api/agents.
    stok = client.post("/api/auth/login", json={
        "email": "operateur@safecity.local", "password": "safecity123"}).get_json()["token"]
    hs = {"Authorization": "Bearer " + stok}
    rs = client.post("/api/auth/me/avatar", json={"photo": _TEST_PNG}, headers=hs)
    assert rs.status_code == 200 and rs.get_json()["avatar_url"]

    agents = client.get("/api/agents?role=agent", headers=hs).get_json()
    assert agents and "avatar_url" in agents[0]   # champ présent (None si pas de photo)

    citizens = client.get("/api/citizens", headers=hs).get_json()
    awa = next(c for c in citizens if c["name"] == "Awa")
    assert awa["avatar_url"] is None   # supprimée plus haut

    # Type non autorisé refusé.
    bad = "data:text/plain;base64," + __import__("base64").b64encode(b"x").decode()
    assert client.post("/api/auth/me/avatar", json={"photo": bad}, headers=hc).status_code == 400


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


def test_register_email_optional_direct_activation():
    """L'inscription est directe (sans code) : l'e-mail est optionnel et le
    compte est actif immédiatement."""
    _, client = make_client()
    r = client.post("/api/auth/register", json={
        "name": "Sans Mail", "phone": "+243830000111", "password": "secret1",
        "consent": True})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["user"]["phone_verified"] is True
    assert r.get_json().get("token")
    # /api/meta : plus d'e-mail obligatoire.
    assert client.get("/api/meta").get_json()["email_required"] is False


def test_sms_gateway_detection_and_twilio_removed():
    """Orange est détecté comme passerelle SMS ; Twilio a bien été retiré."""
    from backend.config import get_config
    from backend.services import notifications
    app, _ = make_client()
    with app.app_context():
        assert notifications.sms_configured() is False
        app.config["ORANGE_CLIENT_ID"] = "id"
        app.config["ORANGE_CLIENT_SECRET"] = "secret"
        app.config["ORANGE_SENDER"] = "tel:+243999999999"
        assert notifications.sms_configured() is True
    assert "TWILIO_SID" not in app.config
    cfg = get_config("testing")
    assert not hasattr(cfg, "TWILIO_SID")
    assert not hasattr(cfg, "TWILIO_FROM")
    assert hasattr(cfg, "ORANGE_CLIENT_ID")


def test_messages_participants_endpoint():
    """L'onglet Infos liste les personnels avec présence et statut de lecture."""
    from datetime import datetime, timedelta
    from backend.extensions import db
    from backend.models import User
    app, client = make_client()
    h = _login(client)
    client.post("/api/messages", json={"text": "Coucou"}, headers=h)
    with app.app_context():
        db.session.add(User(name="Vu", email="vu2@safecity.local", role="agent",
                            messages_seen_at=datetime.utcnow() + timedelta(seconds=3)))
        db.session.commit()
    p = client.get("/api/messages/participants", headers=h).get_json()
    assert isinstance(p, list) and len(p) >= 1
    row = [u for u in p if u["name"] == "Vu"][0]
    assert row["read_latest"] is True and row["online"] is False and "role" in row


def test_message_read_receipt():
    """Un message passe à read=True quand un autre participant a consulté la
    messagerie après son envoi ; POST /api/messages/read répond 200."""
    from datetime import datetime, timedelta
    from backend.extensions import db
    from backend.models import User
    app, client = make_client()
    h = _login(client)
    mid = client.post("/api/messages", json={"text": "Salut"}, headers=h).get_json()["id"]
    before = [m for m in client.get("/api/messages", headers=h).get_json() if m["id"] == mid][0]
    assert before["read"] is False
    with app.app_context():
        db.session.add(User(name="Ag", email="ag@safecity.local", role="agent",
                            messages_seen_at=datetime.utcnow() + timedelta(seconds=2)))
        db.session.commit()
    after = [m for m in client.get("/api/messages", headers=h).get_json() if m["id"] == mid][0]
    assert after["read"] is True
    assert client.post("/api/messages/read", headers=h).status_code == 200


def test_video_message_accepted():
    """Un message peut porter une vidéo (mp4) ; quicktime est normalisé en .mov."""
    import base64
    _, client = make_client()
    h = _login(client)
    raw = base64.b64encode(b"\x00\x00\x00\x18ftypmp42").decode()
    r = client.post("/api/messages", json={"video": "data:video/mp4;base64," + raw}, headers=h)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["video_url"].split("?")[0].endswith(".mp4")
    q = client.post("/api/messages", json={"video": "data:video/quicktime;base64," + raw}, headers=h)
    assert q.get_json()["video_url"].split("?")[0].endswith(".mov")


def test_voice_message_mp4_accepted_as_m4a():
    """Le poste opérateur (Windows/QtMultimedia) envoie du audio/mp4 : il doit
    être accepté et stocké en .m4a (même conteneur MP4/AAC que .m4a)."""
    import base64
    _, client = make_client()
    h = _login(client)
    durl = "data:audio/mp4;base64," + base64.b64encode(b"\x00\x00\x00\x20ftypM4A ").decode()
    r = client.post("/api/messages", json={"voice": durl, "voice_duration": 11}, headers=h)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["voice_url"].split("?")[0].endswith(".m4a")


def _tok(client, email):
    t = client.post("/api/auth/login", json={"email": email, "password": "safecity123"})
    return {"Authorization": "Bearer " + t.get_json()["token"]}


def test_false_alarm_flow_and_journal():
    """Fausse alerte : motif obligatoire, clôture, avertissement au prochain
    signalement du même citoyen, annulation réservée au superviseur, et journal
    complet de l'intervention (qui / rôle / quand)."""
    _, client = make_client()
    ho = _tok(client, "operateur@safecity.local")
    a = client.post("/api/alerts", json={"type": "braquage", "lat": -11.66, "lng": 27.48,
                                         "reporter_name": "Jean", "reporter_phone": "+243810000001"}
                    ).get_json()
    aid = a["id"]
    agent = client.get("/api/agents?role=agent", headers=ho).get_json()[0]
    client.post(f"/api/alerts/{aid}/assign-agent", json={"agent_id": agent["id"]}, headers=ho)

    # Motif obligatoire ; anonyme / agent refusés.
    assert client.post(f"/api/alerts/{aid}/false-alarm", json={}, headers=ho).status_code == 400
    assert client.post(f"/api/alerts/{aid}/false-alarm", json={"reason": "canular"}).status_code == 401
    ha = _tok(client, "agent1@safecity.local")
    assert client.post(f"/api/alerts/{aid}/false-alarm", json={"reason": "canular"},
                       headers=ha).status_code == 403
    r = client.post(f"/api/alerts/{aid}/false-alarm", json={"reason": "Canular téléphonique"},
                    headers=ho)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["false_alarm"] and d["status"] == "cloturee"
    assert d["false_alarm_reason"] == "Canular téléphonique" and d["false_alarm_by"]
    # L'agent est libéré.
    ag = [x for x in client.get("/api/agents?role=agent", headers=ho).get_json()
          if x["id"] == agent["id"]][0]
    assert ag["availability"] == "available"

    # Filtre « fausses alertes » et suivi citoyen (sans motif interne).
    lst = client.get("/api/alerts?false_alarm=1", headers=ho).get_json()
    assert lst["total"] == 1 and lst["items"][0]["id"] == aid
    tr = client.get(f"/api/alerts/track/{a['reference']}").get_json()
    assert tr["false_alarm"] is True and "false_alarm_reason" not in tr

    # Nouveau signalement du même numéro : avertissement (jamais de blocage).
    b = client.post("/api/alerts", json={"type": "incendie", "lat": -11.60, "lng": 27.40,
                                         "reporter_phone": "+243810000001"})
    assert b.status_code == 201
    det = client.get(f"/api/alerts/{b.get_json()['id']}", headers=ho).get_json()
    assert det["reporter_false_alarms"] == 1

    # Annulation : opérateur refusé, superviseur avec raison obligatoire.
    assert client.delete(f"/api/alerts/{aid}/false-alarm", json={"reason": "erreur"},
                         headers=ho).status_code == 403
    hs = _tok(client, "superviseur@safecity.local")
    assert client.delete(f"/api/alerts/{aid}/false-alarm", json={},
                         headers=hs).status_code == 400
    c = client.delete(f"/api/alerts/{aid}/false-alarm", json={"reason": "Vérifié sur place"},
                      headers=hs)
    assert c.status_code == 200 and c.get_json()["false_alarm"] is False

    # Journal de l'intervention : chronologique, avec auteur et rôle.
    j = client.get(f"/api/alerts/{aid}/journal", headers=ho)
    assert j.status_code == 200
    actions = [e["action"] for e in j.get_json()]
    assert actions[:2] == ["alert_created", "agent_assigned"]
    assert "false_alarm_marked" in actions and actions[-1] == "false_alarm_cancelled"
    roles = {e["action"]: e["role"] for e in j.get_json()}
    assert roles["alert_created"] == "Citoyen" and roles["agent_assigned"] == "Opérateur"
    assert roles["false_alarm_cancelled"] == "Superviseur"
    assert client.get(f"/api/alerts/{aid}/journal").status_code == 401

    # Audit global filtrable par incident (superviseur).
    au = client.get(f"/api/audit?alert_id={aid}", headers=hs).get_json()
    assert au and all(e["alert_id"] == aid for e in au)


def test_intervention_actions_are_journaled():
    _, client = make_client()
    client.post("/api/alerts", json={"type": "accident", "lat": -11.66, "lng": 27.48})
    ha = _tok(client, "agent1@safecity.local")
    assert client.post("/api/alerts/1/accept", headers=ha).status_code == 200
    assert client.post("/api/alerts/1/complete", headers=ha).status_code == 200
    j = client.get("/api/alerts/1/journal", headers=ha).get_json()
    actions = [e["action"] for e in j]
    assert actions == ["alert_created", "intervention_accepted", "intervention_completed"]
    assert j[1]["role"] == "Agent" and j[1]["actor"]


def test_security_overview_permissions():
    _, client = make_client()
    client.post("/api/auth/login", json={"email": "x@x.com", "password": "faux"})
    assert client.get("/api/security/overview").status_code == 401
    assert client.get("/api/security/overview",
                      headers=_tok(client, "agent1@safecity.local")).status_code == 403
    r = client.get("/api/security/overview", headers=_tok(client, "operateur@safecity.local"))
    assert r.status_code == 200
    d = r.get_json()
    roles = {x["role"]: x for x in d["roles"]}
    assert set(roles) >= {"citizen", "agent", "operator", "supervisor", "admin"}
    assert roles["operator"]["users"] >= 1 and roles["citizen"]["permissions"] == []
    assert d["activity"]["failed_logins_24h"] >= 1 and d["activity"]["logins_24h"] >= 1
    assert "bcrypt" in d["authentication"]["password_hashing"]
    assert d["data_protection"]["retention_days"]


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
