"""Génère des alertes de démonstration pour tester SafeCity.

Envoie plusieurs alertes réalistes au backend afin d'alimenter le tableau de
bord et la carte du poste opérateur.

Usage :
    python scripts/simulate_alerts.py [URL_BACKEND]
"""
import json
import random
import sys
import time
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"

# Autour de Kinshasa (démonstration).
SAMPLES = [
    ("vol", "On m'a volé mon téléphone à l'arrêt de bus", -4.3280, 15.3150),
    ("braquage", "Un homme armé menace les clients de la boutique", -4.3400, 15.3300),
    ("incendie", "Il y a le feu dans un immeuble, beaucoup de fumée", -4.3120, 15.3050),
    ("accident", "Collision entre une moto et un taxi, un blessé", -4.3350, 15.3220),
    ("violence", "Bagarre violente entre plusieurs personnes", -4.3210, 15.3125),
    ("autre", "Situation suspecte près du marché", -4.3300, 15.3400),
]


def send(sample):
    danger, desc, lat, lng = sample
    payload = {
        "type": danger,
        "description": desc,
        "lat": lat + random.uniform(-0.002, 0.002),
        "lng": lng + random.uniform(-0.002, 0.002),
    }
    req = urllib.request.Request(
        API + "/api/alerts",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(f"  ✔ #{data['id']} {data['type']:10s} urgence={data['urgency']:8s} "
              f"IA={data['ai_category']:9s} dist={data['distance_m']} m")


def main():
    print(f"Envoi d'alertes de démonstration vers {API} …")
    for s in SAMPLES:
        try:
            send(s)
        except Exception as e:
            print("  [x] échec :", e)
        time.sleep(0.4)
    print("Terminé.")


if __name__ == "__main__":
    main()
