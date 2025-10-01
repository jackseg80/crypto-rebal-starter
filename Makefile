# Makefile — Crypto Rebal Starter
# Commandes utiles pour développement et qualité

.PHONY: help setup qa docs test clean

help:
	@echo "Commandes disponibles:"
	@echo "  make setup   - Installer environnement + hooks pre-commit"
	@echo "  make qa      - Exécuter tous les checks qualité"
	@echo "  make docs    - Régénérer la documentation API"
	@echo "  make test    - Lancer les tests unitaires"
	@echo "  make clean   - Nettoyer fichiers temporaires"

setup:
	@echo "[*] Installation environnement virtuel..."
	python -m venv .venv
	@echo "[*] Installation dépendances..."
ifeq ($(OS),Windows_NT)
	.venv\Scripts\python.exe -m pip install --upgrade pip
	.venv\Scripts\python.exe -m pip install -r requirements.txt
	.venv\Scripts\python.exe -m pip install pre-commit
	@echo "[*] Installation hooks pre-commit..."
	.venv\Scripts\pre-commit.exe install
else
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.txt
	.venv/bin/python -m pip install pre-commit
	@echo "[*] Installation hooks pre-commit..."
	.venv/bin/pre-commit install
endif
	@echo "[✓] Setup complet! Activer venv: source .venv/bin/activate (Linux/Mac) ou .venv\Scripts\Activate.ps1 (Windows)"

qa:
	@echo "[*] Régénération API_REFERENCE.md..."
ifeq ($(OS),Windows_NT)
	.venv\Scripts\python.exe tools/gen_api_reference.py
	@echo "[*] Scan liens cassés..."
	.venv\Scripts\python.exe tools/gen_broken_refs.py
	@echo "[*] Exécution hooks pre-commit sur tous fichiers..."
	.venv\Scripts\pre-commit.exe run --all-files
else
	.venv/bin/python tools/gen_api_reference.py
	@echo "[*] Scan liens cassés..."
	.venv/bin/python tools/gen_broken_refs.py
	@echo "[*] Exécution hooks pre-commit sur tous fichiers..."
	.venv/bin/pre-commit run --all-files
endif
	@echo "[✓] Checks qualité terminés!"

docs:
	@echo "[*] Régénération docs/API_REFERENCE.md..."
ifeq ($(OS),Windows_NT)
	.venv\Scripts\python.exe tools/gen_api_reference.py
else
	.venv/bin/python tools/gen_api_reference.py
endif
	@echo "[✓] API_REFERENCE.md régénéré. Vérifie le diff avant commit."

test:
	@echo "[*] Tests unitaires..."
ifeq ($(OS),Windows_NT)
	.venv\Scripts\python.exe -m pytest tests/unit -q
else
	.venv/bin/python -m pytest tests/unit -q
endif

clean:
	@echo "[*] Nettoyage fichiers temporaires..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "[✓] Nettoyage terminé!"
