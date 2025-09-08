#!/usr/bin/env python3
"""
Script pour lancer les tests ML du crypto-rebal-starter
Usage: python run_ml_tests.py [options]
"""

import sys
import subprocess
import argparse
from pathlib import Path

def run_tests(test_type="all", verbose=False, coverage=False, markers=None):
    """
    Lance les tests ML avec les options spécifiées
    
    Args:
        test_type: Type de tests à lancer ("unit", "integration", "all")
        verbose: Mode verbose
        coverage: Générer un rapport de couverture
        markers: Marqueurs pytest spécifiques
    """
    
    # Construire la commande pytest
    cmd = ["python", "-m", "pytest", "tests/ml/"]
    
    # Options de base
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Couverture de code
    if coverage:
        cmd.extend([
            "--cov=services.ml_pipeline_manager_optimized",
            "--cov=api.unified_ml_endpoints", 
            "--cov-report=html:htmlcov",
            "--cov-report=term"
        ])
    
    # Marqueurs spécifiques
    if markers:
        cmd.extend(["-m", markers])
    elif test_type != "all":
        if test_type == "unit":
            cmd.extend(["-m", "not integration"])
        elif test_type == "integration":
            cmd.extend(["-m", "integration"])
    
    # Afficher uniquement les erreurs et échecs par défaut
    if not verbose:
        cmd.extend(["--tb=short"])
    
    print(f"🧪 Lancement des tests ML ({test_type})...")
    print(f"📝 Commande: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("-" * 50)
            print("✅ Tous les tests ML ont réussi!")
        else:
            print("-" * 50)
            print("❌ Certains tests ML ont échoué.")
            
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrompus par l'utilisateur")
        return 1
    except Exception as e:
        print(f"❌ Erreur lors du lancement des tests: {e}")
        return 1


def run_performance_tests():
    """Lance les tests de performance spécifiques"""
    cmd = [
        "python", "-m", "pytest", "tests/ml/",
        "-v", "-m", "performance",
        "--durations=10"
    ]
    
    print("🚀 Lancement des tests de performance ML...")
    print(f"📝 Commande: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode
    except Exception as e:
        print(f"❌ Erreur lors des tests de performance: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Lancer les tests ML")
    parser.add_argument(
        "--type", "-t",
        choices=["unit", "integration", "all"],
        default="all",
        help="Type de tests à lancer"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbose"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true", 
        help="Générer un rapport de couverture"
    )
    parser.add_argument(
        "--markers", "-m",
        help="Marqueurs pytest spécifiques (ex: 'slow', 'ml_models')"
    )
    parser.add_argument(
        "--performance", "-p",
        action="store_true",
        help="Lancer les tests de performance"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Tests rapides seulement (sans intégration)"
    )
    
    args = parser.parse_args()
    
    if args.performance:
        return run_performance_tests()
    
    test_type = args.type
    if args.quick:
        test_type = "unit"
    
    return run_tests(
        test_type=test_type,
        verbose=args.verbose,
        coverage=args.coverage,
        markers=args.markers
    )


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)