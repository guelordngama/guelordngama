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
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise RuntimeError(
                f"Backend injoignable ({reason}). Le serveur est-il démarré "
                f"(python -m backend.server) et accessible sur {self.base_url} ?"
            ) from e

    def login(self, email, password):
        res = self._request("POST", "/api/auth/login",
                            {"email": email, "password": password})
        self.token = res.get("token")
        return res.get("user")

    def get_alerts(self, status=None, filters=None):
        import urllib.parse

        params = {}
        if status:
            params["status"] = status
        if filters:
            params.update({k: v for k, v in filters.items() if v})
        path = "/api/alerts"
        if params:
            path += "?" + urllib.parse.urlencode(params)
        return self._request("GET", path)

    def get_analytics(self, period="month"):
        return self._request("GET", f"/api/analytics?period={period}", auth=True)

    def get_messages(self, limit=50):
        return self._request("GET", f"/api/messages?limit={limit}", auth=True)

    def send_message(self, text, alert_id=None, attachment=None):
        body = {"text": text}
        if alert_id:
            body["alert_id"] = alert_id
        if attachment:
            body["attachment"] = attachment
        return self._request("POST", "/api/messages", body, auth=True)

    def download_export(self, fmt, dest_path, filters=None):
        import urllib.parse

        path = f"/api/export/alerts.{fmt}"
        if filters:
            qs = urllib.parse.urlencode({k: v for k, v in filters.items() if v})
            if qs:
                path += "?" + qs
        url = self.base_url + path
        headers = {"Authorization": "Bearer " + self.token} if self.token else {}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{e.code}: {e.read().decode('utf-8', 'ignore')}") from e
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return dest_path

    def create_agent(self, data):
        return self._request("POST", "/api/agents", data, auth=True)

    def update_agent(self, agent_id, data):
        return self._request("PATCH", f"/api/agents/{agent_id}", data, auth=True)

    def delete_agent(self, agent_id):
        return self._request("DELETE", f"/api/agents/{agent_id}", auth=True)

    def get_stats(self):
        return self._request("GET", "/api/stats")

    def get_teams(self):
        return self._request("GET", "/api/teams")

    def get_agents(self):
        return self._request("GET", "/api/agents", auth=True)

    def get_citizens(self):
        return self._request("GET", "/api/citizens", auth=True)

    def download_report(self, period, dest_path):
        """Télécharge le rapport PDF de la période vers dest_path."""
        url = f"{self.base_url}/api/reports/pdf?period={period}"
        headers = {"Authorization": "Bearer " + self.token} if self.token else {}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{e.code}: {e.read().decode('utf-8', 'ignore')}") from e
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return dest_path

    def assign_team(self, alert_id, team_id):
        return self._request("POST", f"/api/alerts/{alert_id}/assign",
                            {"team_id": team_id}, auth=True)

    def close_alert(self, alert_id):
        return self._request("POST", f"/api/alerts/{alert_id}/close",
                            {}, auth=True)

    def assign_agent(self, alert_id, agent_id):
        return self._request("POST", f"/api/alerts/{alert_id}/assign-agent",
                            {"agent_id": agent_id}, auth=True)

    # ------------------------------------------------------------------ #
    # Temps réel
    # ------------------------------------------------------------------ #
    def on(self, event, callback):
        """Enregistre un callback pour un événement Socket.IO."""
        self._handlers[event] = callback

    def connect_realtime(self):
        if not SOCKETIO_AVAILABLE:
            return False
        # reconnection=True gère les coupures APRÈS une première connexion
        # réussie ; la boucle de _connect_thread gère l'échec initial.
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
        # Transport "polling" uniquement : le backend par défaut tourne sous
        # Waitress (WSGI), qui ne gère PAS les websockets. Tenter une montée en
        # websocket ferait échouer/tomber la connexion (indicateur "Hors ligne").
        # Boucle de reconnexion pour survivre à un démarrage plus lent du backend.
        import time

        for attempt in range(1, 61):  # ~3 min de tentatives (thread daemon)
            try:
                self.sio.connect(self.base_url, transports=["polling"])
                return  # connecté : l'événement "connect" passe l'UI en ligne
            except Exception as e:  # pragma: no cover
                if attempt == 1 or attempt % 5 == 0:
                    print(f"[SafeCity] Connexion temps réel (essai {attempt}) : {e}")
                time.sleep(3)
