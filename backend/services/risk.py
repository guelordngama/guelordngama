"""Zones à risque : carte de chaleur et bilan par commune (aide à la décision
de la mairie pour répartir les patrouilles).

Périmètre : incidents réels uniquement — les doublons (même incident signalé par
plusieurs citoyens), les fausses alertes et les alertes annulées par le citoyen
sont exclus, pour ne pas fausser la lecture. Aucune donnée personnelle n'est
exposée : seulement des positions arrondies (~11 m), types, urgences et heures.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from ..models import Alert, to_local

# Les 7 communes de Lubumbashi (même liste que les patrouilles de commune).
COMMUNES = ["Lubumbashi", "Kamalondo", "Katuba", "Kenya", "Kampemba", "Ruashi", "Annexe"]
UNKNOWN = "Non localisée"

URGENCY_WEIGHT = {"faible": 1, "moyenne": 2, "haute": 3, "critique": 4}

# Tranches horaires (heure locale de Lubumbashi).
BANDS = [("nuit", "Nuit (00h–06h)", 0, 6), ("matin", "Matin (06h–12h)", 6, 12),
         ("apres_midi", "Après-midi (12h–18h)", 12, 18), ("soir", "Soir (18h–24h)", 18, 24)]
BAND_LABELS = {k: lbl for k, lbl, _a, _b in BANDS}

_CELL_DEG = 0.003      # ≈ 330 m : taille d'un « point chaud »
_MAX_POINTS = 5000


def band_of(dt):
    h = to_local(dt).hour
    for key, _lbl, a, b in BANDS:
        if a <= h < b:
            return key
    return "nuit"


def normalize_commune(raw):
    """Rattache le nom géocodé à l'une des 7 communes (« Commune de Kenya » →
    « Kenya ») ; sinon conserve le nom tel quel, ou « Non localisée »."""
    name = (raw or "").strip()
    if not name:
        return UNKNOWN
    low = name.lower()
    for c in COMMUNES:
        if low == c.lower() or low.endswith(" " + c.lower()) or low.endswith("'" + c.lower()):
            return c
    return name


def _clamp_days(days):
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 30
    return max(1, min(days, 730))


def _incidents(since, until=None, type_=None):
    q = (Alert.query.filter(Alert.created_at >= since)
         .filter(Alert.duplicate_of_id.is_(None))
         .filter(Alert.false_alarm.is_(False))
         .filter(Alert.cancelled_by_citizen.is_(False)))
    if until is not None:
        q = q.filter(Alert.created_at < until)
    if type_:
        q = q.filter(Alert.type == type_)
    return q.order_by(Alert.created_at.desc()).all()


def heatmap(days=30, type_=None, band=None):
    """Points pondérés par l'urgence + points chauds (cellules ≈ 330 m)."""
    days = _clamp_days(days)
    since = datetime.utcnow() - timedelta(days=days)
    alerts = [a for a in _incidents(since, type_=type_ or None)
              if a.lat is not None and a.lng is not None
              and (not band or band_of(a.created_at) == band)]
    points = [{"lat": round(a.lat, 4), "lng": round(a.lng, 4),
               "w": URGENCY_WEIGHT.get(a.urgency, 2), "type": a.type}
              for a in alerts[:_MAX_POINTS]]

    cells = defaultdict(list)
    for a in alerts:
        cells[(round(a.lat / _CELL_DEG), round(a.lng / _CELL_DEG))].append(a)
    hotspots = []
    for group in cells.values():
        place = Counter(a.neighborhood or normalize_commune(a.commune) for a in group
                        if (a.neighborhood or a.commune))
        hotspots.append({
            "lat": round(sum(a.lat for a in group) / len(group), 4),
            "lng": round(sum(a.lng for a in group) / len(group), 4),
            "count": len(group),
            "score": sum(URGENCY_WEIGHT.get(a.urgency, 2) for a in group),
            "label": place.most_common(1)[0][0] if place else "Zone sans adresse",
        })
    hotspots.sort(key=lambda h: (-h["score"], -h["count"]))
    return {"days": days, "total": len(alerts), "points": points, "hotspots": hotspots[:8]}


def _level(score, top):
    if not score or not top:
        return "faible"
    ratio = score / top
    return "élevé" if ratio >= 0.66 else "moyen" if ratio >= 0.33 else "faible"


def communes_report(days=30, type_=None):
    """Bilan par commune sur la période, comparé à la période précédente, avec
    niveau de risque relatif et recommandations d'affectation de patrouilles."""
    days = _clamp_days(days)
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    current = _incidents(since, type_=type_)
    previous = _incidents(since - timedelta(days=days), until=since, type_=type_)

    prev_count = Counter(normalize_commune(a.commune) for a in previous)
    groups = defaultdict(list)
    for a in current:
        groups[normalize_commune(a.commune)].append(a)
    for c in COMMUNES:          # les 7 communes figurent toujours, même à zéro
        groups.setdefault(c, [])

    rows = []
    for name, items in groups.items():
        bands = Counter(band_of(a.created_at) for a in items)
        types = Counter(a.type for a in items)
        hoods = Counter(a.neighborhood for a in items if a.neighborhood)
        done = [(a.closed_at - a.created_at).total_seconds() / 60.0
                for a in items if a.status == "cloturee" and a.closed_at]
        score = sum(URGENCY_WEIGHT.get(a.urgency, 2) for a in items)
        prev = prev_count.get(name, 0)
        rows.append({
            "commune": name, "count": len(items), "score": score,
            "urgent": sum(1 for a in items if a.urgency in ("haute", "critique")),
            "by_type": dict(types.most_common()),
            "by_band": {k: bands.get(k, 0) for k, *_ in BANDS},
            "peak_band": (max(bands, key=bands.get) if bands else None),
            "top_type": types.most_common(1)[0][0] if types else None,
            "top_neighborhoods": [{"name": n, "count": c} for n, c in hoods.most_common(3)],
            "resolved": sum(1 for a in items if a.status == "cloturee"),
            "avg_response_min": round(sum(done) / len(done), 1) if done else None,
            "previous_count": prev,
            "trend_pct": (round((len(items) - prev) * 100.0 / prev) if prev else None),
        })
    top = max((r["score"] for r in rows), default=0)
    total = len(current)
    for r in rows:
        r["risk"] = _level(r["score"], top)
        r["share_pct"] = round(r["count"] * 100.0 / total) if total else 0
    rows.sort(key=lambda r: (-r["score"], -r["count"], r["commune"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    return {"days": days, "total": total, "previous_total": len(previous),
            "communes": rows, "recommendations": _recommendations(rows, current, total)}


def _recommendations(rows, current, total):
    recs = []
    if not total:
        return ["Aucun incident sur la période : pas de recommandation."]
    for r in [r for r in rows if r["count"]][:3]:
        peak = BAND_LABELS.get(r["peak_band"], "—")
        hood = r["top_neighborhoods"][0]["name"] if r["top_neighborhoods"] else None
        trend = ""
        if r["trend_pct"] is not None and abs(r["trend_pct"]) >= 20:
            trend = f" ({'+' if r['trend_pct'] > 0 else ''}{r['trend_pct']} % vs période précédente)"
        recs.append(
            f"Priorité n°{r['rank']} — {r['commune']} : {r['count']} incident(s), "
            f"{r['share_pct']} % du total{trend}. Pic : {peak}"
            + (f" ; quartier le plus touché : {hood}" if hood else "")
            + (f" ; type dominant : {r['top_type']}." if r["top_type"] else "."))
    by_band = defaultdict(Counter)
    for a in current:
        by_band[band_of(a.created_at)][normalize_commune(a.commune)] += 1
    for key, lbl, _a, _b in BANDS:
        counter = by_band.get(key)
        n = sum(counter.values()) if counter else 0
        if n >= 3:
            commune, c = counter.most_common(1)[0]
            recs.append(f"{lbl} : {commune} concentre {round(c * 100 / n)} % des incidents "
                        f"({c} sur {n}) — y renforcer la présence à cette tranche horaire.")
    return recs
