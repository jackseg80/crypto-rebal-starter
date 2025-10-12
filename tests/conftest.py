"""
Configuration globale pytest pour tous les tests.

Ajoute le répertoire racine du projet au PYTHONPATH
pour permettre les imports relatifs (ex: from services.xxx import ...)
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine du projet au sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
