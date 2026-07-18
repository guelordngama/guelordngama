# ===== SafeCity backend — image de production =====
FROM python:3.11-slim AS base

# Bonnes pratiques Python en conteneur.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SAFECITY_ENV=production \
    SAFECITY_HOST=0.0.0.0 \
    SAFECITY_PORT=5000

WORKDIR /app

# Dépendances système minimales (build de certaines roues) puis nettoyage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python (couche cache).
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install psycopg2-binary waitress

# Code applicatif.
COPY backend/ ./backend/
COPY web/ ./web/

# Utilisateur non-root.
RUN useradd --create-home --uid 10001 safecity \
    && mkdir -p backend/uploads && chown -R safecity:safecity /app
USER safecity

EXPOSE 5000

# Sonde de santé.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/api/health || exit 1

# Waitress sert l'API + Socket.IO (long-polling).
CMD ["python", "-m", "backend.server"]
