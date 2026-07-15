"""Classification IA des incidents SafeCity.

Deux responsabilités :
  1. Classer la description libre d'une alerte dans une catégorie de danger.
  2. Estimer le niveau d'urgence (faible / moyenne / haute / critique).

Le modèle repose sur scikit-learn (TF-IDF + Naive Bayes) entraîné au démarrage
sur un petit jeu de données amorce en français. Si scikit-learn n'est pas
installé, un moteur de secours à base de mots-clés prend le relais afin que le
backend reste fonctionnel en toute circonstance.
"""
import re

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - dépend de l'environnement
    SKLEARN_AVAILABLE = False


# --- Jeu de données amorce (français) : (texte, catégorie) ---
SEED_DATA = [
    ("on m'a volé mon téléphone dans la rue", "vol"),
    ("vol à l'arraché de mon sac", "vol"),
    ("pickpocket au marché il a pris mon portefeuille", "vol"),
    ("cambriolage chez le voisin", "vol"),
    ("un homme armé nous menace avec un pistolet", "braquage"),
    ("braquage à main armée dans la boutique", "braquage"),
    ("ils ont un couteau et exigent de l'argent", "braquage"),
    ("attaque à main armée à la station service", "braquage"),
    ("il y a le feu dans la maison", "incendie"),
    ("de la fumée et des flammes dans l'immeuble", "incendie"),
    ("incendie dans le quartier ça brûle", "incendie"),
    ("un feu s'est déclaré au marché", "incendie"),
    ("accident de voiture grave sur l'avenue", "accident"),
    ("collision entre une moto et un taxi blessés", "accident"),
    ("un piéton a été renversé par une voiture", "accident"),
    ("accident de la route plusieurs blessés", "accident"),
    ("bagarre violente entre deux personnes", "violence"),
    ("un homme frappe une femme dans la rue", "violence"),
    ("des coups et des cris dispute violente", "violence"),
    ("agression physique quelqu'un est blessé", "violence"),
    ("il y a un problème je ne sais pas quoi dire", "autre"),
    ("situation suspecte dans le quartier", "autre"),
    ("besoin d'aide urgente", "autre"),
    ("rassemblement suspect près du pont", "autre"),
]

# Mots-clés à forte gravité pour l'estimation d'urgence.
CRITICAL_WORDS = [
    "armé", "arme", "pistolet", "couteau", "sang", "mort", "tué", "tuer",
    "feu", "flamme", "brûle", "incendie", "blessé", "blessés", "urgent",
    "urgence", "attaque", "braquage", "coups de feu", "explosion",
]
HIGH_WORDS = [
    "violence", "bagarre", "frappe", "agression", "accident", "collision",
    "menace", "renversé", "danger",
]

# Urgence de base par catégorie.
CATEGORY_BASE_URGENCY = {
    "braquage": "critique",
    "incendie": "critique",
    "violence": "haute",
    "accident": "haute",
    "vol": "moyenne",
    "autre": "faible",
}

URGENCY_ORDER = ["faible", "moyenne", "haute", "critique"]

# Moteur de secours par mots-clés (si scikit-learn absent).
KEYWORD_RULES = {
    "braquage": ["arm", "pistolet", "couteau", "braqu", "main armée"],
    "incendie": ["feu", "flamme", "brûl", "incendie", "fumée"],
    "accident": ["accident", "collision", "renvers", "voiture", "moto", "route"],
    "violence": ["bagarre", "frappe", "agress", "violent", "coups", "dispute"],
    "vol": ["vol", "volé", "pickpocket", "cambriol", "arrach", "portefeuille"],
}


def _normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


class IncidentClassifier:
    """Classe une alerte : catégorie + urgence + score de confiance."""

    def __init__(self):
        self._pipeline = None
        if SKLEARN_AVAILABLE:
            self._train()

    def _train(self):
        texts = [t for t, _ in SEED_DATA]
        labels = [c for _, c in SEED_DATA]
        self._pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
                ("clf", MultinomialNB(alpha=0.3)),
            ]
        )
        self._pipeline.fit(texts, labels)

    # --- Catégorie ---
    def _predict_category_ml(self, text):
        proba = self._pipeline.predict_proba([text])[0]
        classes = self._pipeline.named_steps["clf"].classes_
        idx = proba.argmax()
        return str(classes[idx]), float(proba[idx])

    def _predict_category_keywords(self, text):
        best, best_hits = "autre", 0
        for category, kws in KEYWORD_RULES.items():
            hits = sum(1 for kw in kws if kw in text)
            if hits > best_hits:
                best, best_hits = category, hits
        score = min(1.0, 0.4 + 0.2 * best_hits) if best_hits else 0.3
        return best, score

    # --- Urgence ---
    def _predict_urgency(self, text, category):
        base = CATEGORY_BASE_URGENCY.get(category, "faible")
        level = URGENCY_ORDER.index(base)
        if any(w in text for w in CRITICAL_WORDS):
            level = max(level, URGENCY_ORDER.index("critique"))
        elif any(w in text for w in HIGH_WORDS):
            level = max(level, URGENCY_ORDER.index("haute"))
        return URGENCY_ORDER[level]

    def classify(self, description, declared_type=None):
        """Analyse une description libre.

        `declared_type` est le type choisi par le citoyen dans l'app ; il sert
        de repli quand la description est vide ou peu informative.

        Retourne un dict : {category, urgency, score, engine}.
        """
        text = _normalize(description)
        if not text:
            category = (declared_type or "autre").lower()
            return {
                "category": category,
                "urgency": CATEGORY_BASE_URGENCY.get(category, "faible"),
                "score": 0.2,
                "engine": "declared",
            }

        if self._pipeline is not None:
            category, score = self._predict_category_ml(text)
            engine = "sklearn"
        else:
            category, score = self._predict_category_keywords(text)
            engine = "keywords"

        # Si le citoyen a explicitement déclaré un type et que l'IA hésite,
        # on privilégie le type déclaré.
        if declared_type and declared_type.lower() in CATEGORY_BASE_URGENCY:
            if score < 0.45:
                category = declared_type.lower()
                score = max(score, 0.5)

        urgency = self._predict_urgency(text, category)
        return {
            "category": category,
            "urgency": urgency,
            "score": round(score, 3),
            "engine": engine,
        }


# Instance partagée (chargée une fois au démarrage du backend).
_classifier = None


def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = IncidentClassifier()
    return _classifier
