# ===== SafeCity — raccourcis de développement =====
.PHONY: help install dev serve test lint web simulate docker-up docker-down

help:
	@echo "Cibles disponibles :"
	@echo "  install     Installer les dépendances backend"
	@echo "  dev         Lancer le backend (serveur de développement)"
	@echo "  serve       Lancer le backend (Waitress, production)"
	@echo "  web         Servir l'application citoyenne (port 8080)"
	@echo "  test        Lancer les tests"
	@echo "  simulate    Générer des alertes de démonstration"
	@echo "  docker-up   Démarrer backend + PostgreSQL (Docker)"
	@echo "  docker-down Arrêter les conteneurs"

install:
	pip install -r requirements.txt

dev:
	python -m backend.app

serve:
	python -m backend.server

web:
	cd web && python -m http.server 8080

test:
	pytest -q || python tests/test_backend.py

simulate:
	python scripts/simulate_alerts.py http://localhost:5000

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
