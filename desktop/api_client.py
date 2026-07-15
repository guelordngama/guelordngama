"""Client réseau du poste opérateur SafeCity.

Encapsule les appels REST vers le backend Flask et l'abonnement temps réel
Socket.IO. Les événements reçus sont relayés via des callbacks pour être
transformés en signaux Qt côté interface.
"""
import json
import threading
import urllib.error
import urllib.request

try:
    import socketio  # python-socketio (client)
    SOCKETIO_AVAILABLE = True
except Exception:  # pragma: no cover
    SOCKETIO_AVAILABLE = False


class ApiClient:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.sio = None
        self._handlers = {}  # event -> callback

    # ------------------------------------------------------------------ #
    # REST
    # ------------------------------------------------------------------ #
    def _request(self, method, path, data=None, auth=False):
        url = self.base_url + path
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")
            raise RuntimeError(f"{e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connexion impossible : {e.reason}") from e

    def login(self, email, password):
        res = self._request("POST", "/api/auth/login",
                            {"email": email, "password": password})
        self.token = res.get("token")
        return res.get("user")

    def get_alerts(self, status=None):
        path = "/api/alerts" + (f"?status={status}" if status else "")
        return self._request("GET", path)

    def get_stats(self):
        return self._request("GET", "/api/stats")

    def get_teams(self):
        return self._request("GET", "/api/teams")

    def assign_team(self, alert_id, team_id):
        return self._request("POST", f"/api/alerts/{alert_id}/assign",
                            {"team_id": team_id}, auth=True)

    def close_alert(self, alert_id):
        return self._request("POST", f"/api/alerts/{alert_id}/close",
                            {}, auth=True)

    # ------------------------------------------------------------------ #
    # Temps réel
    # ------------------------------------------------------------------ #
    def on(self, event, callback):
        """Enregistre un callback pour un événement Socket.IO."""
        self._handlers[event] = callback

    def connect_realtime(self):
        if not SOCKETIO_AVAILABLE:
            return False
        self.sio = socketio.Client(reconnection=True, logger=False)

        @self.sio.event
        def connect():
            cb = self._handlers.get("connect")
            if cb:
                cb()

        @self.sio.event
        def disconnect():
            cb = self._handlers.get("disconnect")
            if cb:
                cb()

        def _make(event):
            def handler(data):
                cb = self._handlers.get(event)
                if cb:
                    cb(data)
            return handler

        for evt in ("new_alert", "alert_updated"):
            self.sio.on(evt, _make(evt))

        # Connexion dans un thread pour ne pas bloquer l'UI.
        threading.Thread(target=self._connect_thread, daemon=True).start()
        return True

    def _connect_thread(self):
        try:
            self.sio.connect(self.base_url, transports=["polling", "websocket"])
        except Exception as e:  # pragma: no cover
            print("[SafeCity] Échec connexion temps réel :", e)
