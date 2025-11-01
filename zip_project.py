import os
import zipfile
from pathlib import Path

# Dossier source et dossier de sortie
source_dir = Path(r"D:\Python\smartfolio")
output_zip = Path(r"D:\Python\smartfolio.zip")

# Patterns/dossiers à exclure
EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".vscode", ".idea", ".vs",  # IDEs
    "node_modules",  # Node dependencies
    "models", "cache", "price_history",  # ML models & caches
    "data",  # Données générées (exclure complètement)
    ".ruff_cache", ".tox", "htmlcov", ".coverage",  # Test/lint artifacts
    "dist", "build", "*.egg-info",  # Build artifacts
    "test-results",  # Playwright test artifacts (44MB: screenshots, videos, traces)
    "e2e-report",  # Playwright HTML report (46MB)
    "html_debug",  # HTML debug pages (732KB)
    "archive",  # Archives de développement (1.4MB: backups, tests obsolètes)
}
EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db",  # OS files
    "*.pyc", "*.pyo", "*.pyd",  # Python compiled
    "*.log", "*.tmp", "*.temp",  # Logs/temp
    "*.bak", "*.backup", "*.swp", "*.swo",  # Backups
    ".env", ".env.local", ".env.production",  # Secrets
    "*.db", "*.sqlite", "*.sqlite3",  # Databases
    "*.zip", "*.tar.gz", "*.rar",  # Archives (dans tests/ uniquement)
    "package-lock.json", "poetry.lock",  # Lock files (optionnel)
    "test-results-latest.json", "e2e-results.json",  # Test results artifacts
    "*.webm", "*.mp4",  # Vidéos de tests
}

def should_exclude(path: Path) -> bool:
    """Retourne True si le chemin doit être exclu du zip."""
    # Exclusion par nom de dossier
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True

    # Exclusion par nom de fichier exact
    if path.name in EXCLUDE_FILES:
        return True

    # Exclusion par pattern (*.ext)
    for pattern in EXCLUDE_FILES:
        if pattern.startswith("*.") and path.suffix == pattern[1:]:
            return True
        elif "*" not in pattern and path.name == pattern:
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
