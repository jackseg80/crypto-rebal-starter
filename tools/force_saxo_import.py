#!/usr/bin/env python3
"""
Force l'import du dernier CSV Saxo uploadé
"""

import sys
import os
from pathlib import Path
import json
import logging

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Activer le logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

from connectors.saxo_import import SaxoImportConnector
from adapters.saxo_adapter import ingest_file

USER_ID = "jack"

def main():
    print("=" * 60)
    print("FORCE IMPORT SAXO")
    print("=" * 60)
    print()

    # 1. Vérifier uploads et imports (en cas de déplacement)
    upload_dir = Path("data/users") / USER_ID / "saxobank" / "uploads"
    imports_dir = Path("data/users") / USER_ID / "saxobank" / "imports"

    csv_files = []

    # Chercher dans uploads d'abord
    if upload_dir.exists():
        csv_files.extend(list(upload_dir.glob("*.csv")))

    # Si rien dans uploads, chercher dans imports
    if not csv_files and imports_dir.exists():
        csv_files.extend(list(imports_dir.glob("*.csv")))
        print(f"[INFO] Fichiers trouves dans imports/")

    if not csv_files:
        print(f"[ERROR] Aucun fichier CSV dans uploads/ ou imports/")
        return

    # Prendre le plus récent
    latest_csv = max(csv_files, key=lambda f: f.stat().st_mtime)
    print(f"[CSV] Fichier trouve: {latest_csv.name}")
    print(f"      Taille: {latest_csv.stat().st_size:,} bytes")
    print()

    # 2. Forcer l'import via l'adapter (qui sauvegarde dans le fichier legacy)
    print("[IMPORT] En cours...")
    try:
        result = ingest_file(str(latest_csv), USER_ID)

        print(f"[DEBUG] Result keys: {list(result.keys())}")
        print(f"[DEBUG] Portfolio ID: {result.get('portfolio', {}).get('portfolio_id')}")
        print(f"[DEBUG] Positions count: {len(result.get('portfolio', {}).get('positions', []))}")
        print(f"[DEBUG] Errors: {result.get('errors', [])[:3]}")

        portfolio = result.get("portfolio", {})
        summary = result.get("summary", {})

        if portfolio.get("positions"):
            print("[SUCCESS] Import reussi !")
            print()
            print(f"   Positions: {portfolio.get('positions_count', 0)}")
            print(f"   Valeur totale: ${portfolio.get('total_value_usd', 0):,.2f}")
            print(f"   Portfolio ID: {portfolio.get('portfolio_id', 'N/A')}")

            if result.get("errors"):
                print(f"   [WARN] {len(result['errors'])} warnings:")
                for err in result['errors'][:3]:  # Show first 3
                    print(f"      {err}")

            print()

            # Afficher top 5
            positions = portfolio.get('positions', [])[:5]
            if positions:
                print("   Top 5 Holdings:")
                for i, pos in enumerate(positions, 1):
                    name = pos.get('name', pos.get('instrument', 'Unknown'))
                    symbol = pos.get('symbol', 'N/A')
                    value = pos.get('market_value_usd', 0)
                    print(f"   {i}. {name} ({symbol}) - ${value:,.2f}")

        else:
            print(f"[ERROR] Import echoue")
            if result.get("errors"):
                for err in result['errors']:
                    print(f"   {err}")

    except Exception as e:
        print(f"[ERROR] Erreur lors de l'import: {e}")
        import traceback
        traceback.print_exc()
        return

    print()
    print("=" * 60)
    print("TERMINE")
    print("=" * 60)
    print()
    print("Prochaines etapes:")
    print("1. Rafraichissez: http://localhost:8000/static/saxo-dashboard.html")
    print("2. Selectionnez le portfolio dans le dropdown")
    print()

if __name__ == "__main__":
    main()
