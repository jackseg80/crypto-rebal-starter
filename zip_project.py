import os
import zipfile
from pathlib import Path

# Dossier source et dossier de sortie
source_dir = Path(r"D:\Python\crypto-rebal-starter")
output_zip = Path(r"D:\Python\crypto-rebal-starter.zip")

# Patterns/dossiers à exclure
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".vscode", "node_modules", "models", "cache", "archive", "price_history"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}

def should_exclude(path: Path) -> bool:
    """Retourne True si le chemin doit être exclu du zip."""
    # Exclusion par nom de dossier
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    # Exclusion par fichier
    if path.name in EXCLUDE_FILES:
        return True
    # Exclusion fichiers compilés / temporaires
    if path.suffix in {".pyc", ".pyo", ".log", ".tmp"}:
        return True
    return False

def zip_project(src: Path, dest_zip: Path):
    # Supprimer le zip existant s'il existe
    if dest_zip.exists():
        dest_zip.unlink()
        print(f"⚠️ Fichier existant supprimé : {dest_zip}")

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in src.rglob("*"):
            if file.is_file() and not should_exclude(file.relative_to(src)):
                zipf.write(file, arcname=file.relative_to(src))
    print(f"✅ Projet zippé dans : {dest_zip}")

if __name__ == "__main__":
    zip_project(source_dir, output_zip)
