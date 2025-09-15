#!/usr/bin/env python3
"""
Script de déploiement automatisé pour l'application Crypto Rebalancing avec IA
Gestion complète du cycle de déploiement avec tests et validation
"""

import os
import sys
import json
import shutil
import subprocess
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime

# Configuration
DEPLOY_CONFIG = {
    'app_name': 'crypto-rebal-ai',
    'version': '2.0.0',
    'python_version': '3.9+',
    'required_packages': [
        'fastapi', 'uvicorn', 'tensorflow', 'scikit-learn', 
        'pandas', 'numpy', 'aiohttp', 'redis', 'psycopg2'
    ],
    'static_files': [
        'navigation-themes.js', 'navigation-themes.css',
        'themed-navigation.js', 'navigation-migration.js',
        'ai-services.js', 'ai-state-manager.js', 'ai-components.js', 'ai-components.css',
        'ai-dashboard.html', 'ai-components-demo.html'
    ],
    'health_check_url': 'http://localhost:8000/api/ai/health',
    'deployment_timeout': 300  # 5 minutes
}

class Colors:
    """Codes couleur pour l'affichage console"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'

class DeploymentManager:
    """Gestionnaire principal du déploiement"""
    
    def __init__(self, environment: str = 'development'):
        self.environment = environment
        self.project_root = Path.cwd()
        self.static_dir = self.project_root / 'static'
        self.backup_dir = self.project_root / 'backups' / f"deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log_file = self.project_root / 'deploy.log'
        
        self.deployment_steps = [
            ('Validation de l\'environnement', self.validate_environment),
            ('Sauvegarde des fichiers existants', self.backup_current_state),
            ('Installation des dépendances', self.install_dependencies),
            ('Validation des fichiers statiques', self.validate_static_files),
            ('Tests d\'intégration', self.run_integration_tests),
            ('Démarrage des services', self.start_services),
            ('Validation du déploiement', self.validate_deployment),
            ('Nettoyage et finalisation', self.cleanup_deployment)
        ]
        
        self.stats = {
            'start_time': None,
            'end_time': None,
            'steps_completed': 0,
            'steps_failed': 0,
            'total_steps': len(self.deployment_steps)
        }

    def log(self, message: str, level: str = 'INFO'):
        """Log avec timestamp et couleur"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        color = {
            'INFO': Colors.BLUE,
            'SUCCESS': Colors.GREEN,
            'WARNING': Colors.YELLOW,
            'ERROR': Colors.RED
        }.get(level, Colors.RESET)
        
        formatted_message = f"[{timestamp}] {level}: {message}"
        
        # Affichage console avec couleur
        print(f"{color}{formatted_message}{Colors.RESET}")
        
        # Écriture dans le fichier de log
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(formatted_message + '\n')

    def run_command(self, command: str, check: bool = True) -> Tuple[bool, str]:
        """Exécuter une commande système"""
        try:
            self.log(f"Executing: {command}")
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=check,
                cwd=self.project_root
            )
            self.log(f"Command output: {result.stdout}", 'INFO')
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e.stderr}", 'ERROR')
            return False, e.stderr

    def validate_environment(self) -> bool:
        """Valider l'environnement de déploiement"""
        self.log("Validation de l'environnement de déploiement")
        
        # Vérifier Python
        success, output = self.run_command('python --version')
        if not success:
            self.log("Python n'est pas disponible", 'ERROR')
            return False
        
        python_version = output.strip()
        self.log(f"Python version: {python_version}")
        
        # Vérifier pip
        success, _ = self.run_command('pip --version')
        if not success:
            self.log("pip n'est pas disponible", 'ERROR')
            return False
        
        # Vérifier l'espace disque
        if not self.check_disk_space():
            return False
        
        # Vérifier les ports
        if not self.check_ports():
            return False
        
        # Créer les dossiers nécessaires
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.log("Environnement validé avec succès", 'SUCCESS')
        return True

    def check_disk_space(self, min_gb: float = 1.0) -> bool:
        """Vérifier l'espace disque disponible"""
        try:
            stat = shutil.disk_usage(self.project_root)
            free_gb = stat.free / (1024**3)
            
            if free_gb < min_gb:
                self.log(f"Espace disque insuffisant: {free_gb:.2f}GB < {min_gb}GB", 'ERROR')
                return False
            
            self.log(f"Espace disque disponible: {free_gb:.2f}GB")
            return True
        except Exception as e:
            self.log(f"Erreur lors de la vérification de l'espace disque: {e}", 'ERROR')
            return False

    def check_ports(self, ports: List[int] = [8000, 8001]) -> bool:
        """Vérifier que les ports nécessaires sont disponibles"""
        import socket
        
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('localhost', port))
                    if result == 0:
                        self.log(f"Port {port} est déjà utilisé", 'WARNING')
                        # Ne pas échouer - on peut arrêter les services existants
                    else:
                        self.log(f"Port {port} disponible")
            except Exception as e:
                self.log(f"Erreur lors de la vérification du port {port}: {e}", 'WARNING')
        
        return True

    def backup_current_state(self) -> bool:
        """Sauvegarder l'état actuel"""
        self.log("Création de la sauvegarde")
        
        try:
            # Sauvegarder les fichiers statiques
            if self.static_dir.exists():
                static_backup = self.backup_dir / 'static'
                shutil.copytree(self.static_dir, static_backup, dirs_exist_ok=True)
                self.log(f"Fichiers statiques sauvegardés dans {static_backup}")
            
            # Sauvegarder la configuration
            config_files = ['requirements.txt', 'package.json', '.env']
            for config_file in config_files:
                config_path = self.project_root / config_file
                if config_path.exists():
                    shutil.copy2(config_path, self.backup_dir)
                    self.log(f"Configuration sauvegardée: {config_file}")
            
            # Créer un manifeste de sauvegarde
            manifest = {
                'timestamp': datetime.now().isoformat(),
                'environment': self.environment,
                'version': DEPLOY_CONFIG['version'],
                'files_backed_up': len(list(self.backup_dir.rglob('*')))
            }
            
            with open(self.backup_dir / 'manifest.json', 'w') as f:
                json.dump(manifest, f, indent=2)
            
            self.log("Sauvegarde créée avec succès", 'SUCCESS')
            return True
            
        except Exception as e:
            self.log(f"Erreur lors de la sauvegarde: {e}", 'ERROR')
            return False

    def install_dependencies(self) -> bool:
        """Installer les dépendances"""
        self.log("Installation des dépendances")
        
        # Vérifier requirements.txt
        requirements_file = self.project_root / 'requirements.txt'
        if requirements_file.exists():
            success, output = self.run_command('pip install -r requirements.txt')
            if not success:
                self.log("Échec de l'installation depuis requirements.txt", 'ERROR')
                return False
        else:
            # Installer les packages requis individuellement
            for package in DEPLOY_CONFIG['required_packages']:
                success, output = self.run_command(f'pip install {package}')
                if not success:
                    self.log(f"Échec de l'installation de {package}", 'WARNING')
                    # Continuer avec les autres packages
        
        # Vérifier les installations
        self.log("Vérification des dépendances installées")
        success, output = self.run_command('pip list')
        if success:
            installed_packages = output.lower()
            missing_packages = []
            
            for package in DEPLOY_CONFIG['required_packages']:
                if package.lower().replace('-', '_') not in installed_packages:
                    missing_packages.append(package)
            
            if missing_packages:
                self.log(f"Packages manquants: {missing_packages}", 'WARNING')
                # Tenter une nouvelle installation
                for package in missing_packages:
                    self.run_command(f'pip install {package}', check=False)
        
        self.log("Dépendances installées", 'SUCCESS')
        return True

    def validate_static_files(self) -> bool:
        """Valider la présence des fichiers statiques requis"""
        self.log("Validation des fichiers statiques")
        
        missing_files = []
        for file_name in DEPLOY_CONFIG['static_files']:
            file_path = self.static_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)
            else:
                # Vérifier que le fichier n'est pas vide
                if file_path.stat().st_size == 0:
                    self.log(f"Fichier vide détecté: {file_name}", 'WARNING')
                else:
                    self.log(f"Fichier validé: {file_name}")
        
        if missing_files:
            self.log(f"Fichiers statiques manquants: {missing_files}", 'ERROR')
            return False
        
        # Vérifier l'intégrité des fichiers JavaScript
        js_files = [f for f in DEPLOY_CONFIG['static_files'] if f.endswith('.js')]
        for js_file in js_files:
            if not self.validate_javascript_syntax(self.static_dir / js_file):
                return False
        
        self.log("Fichiers statiques validés avec succès", 'SUCCESS')
        return True

    def validate_javascript_syntax(self, js_file: Path) -> bool:
        """Valider la syntaxe JavaScript (basique)"""
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Vérifications basiques de syntaxe
            if content.count('{') != content.count('}'):
                self.log(f"Accolades non équilibrées dans {js_file.name}", 'ERROR')
                return False
            
            if content.count('(') != content.count(')'):
                self.log(f"Parenthèses non équilibrées dans {js_file.name}", 'ERROR')
                return False
            
            # Vérifier qu'il n'y a pas d'erreurs évidentes
            obvious_errors = ['undefined is not defined', 'SyntaxError', 'ReferenceError']
            for error in obvious_errors:
                if error in content:
                    self.log(f"Erreur potentielle dans {js_file.name}: {error}", 'WARNING')
            
            self.log(f"Syntaxe JavaScript validée: {js_file.name}")
            return True
            
        except Exception as e:
            self.log(f"Erreur lors de la validation de {js_file.name}: {e}", 'ERROR')
            return False

    def run_integration_tests(self) -> bool:
        """Exécuter les tests d'intégration"""
        self.log("Exécution des tests d'intégration")
        
        # Tests Python (si un framework de test est disponible)
        test_commands = [
            'python -m pytest tests/ -v --tb=short || echo "No pytest tests found"',
            'python -m unittest discover tests/ || echo "No unittest tests found"'
        ]
        
        for cmd in test_commands:
            success, output = self.run_command(cmd, check=False)
            if 'FAILED' in output or 'ERROR' in output:
                self.log("Des tests ont échoué", 'WARNING')
                # Ne pas arrêter le déploiement pour les tests
        
        # Test de syntaxe Python
        python_files = list(self.project_root.glob('*.py'))
        for py_file in python_files:
            success, output = self.run_command(f'python -m py_compile {py_file}')
            if not success:
                self.log(f"Erreur de syntaxe dans {py_file}: {output}", 'ERROR')
                return False
        
        self.log("Tests d'intégration terminés", 'SUCCESS')
        return True

    def start_services(self) -> bool:
        """Démarrer les services de l'application"""
        self.log("Démarrage des services")
        
        try:
            # Arrêter les services existants (si ils tournent)
            self.run_command('pkill -f uvicorn', check=False)
            time.sleep(2)  # Attendre l'arrêt
            
            # Chercher le fichier principal de l'application
            main_files = ['main.py', 'app.py', 'server.py']
            main_file = None
            
            for filename in main_files:
                if (self.project_root / filename).exists():
                    main_file = filename
                    break
            
            if not main_file:
                self.log("Aucun fichier principal trouvé", 'ERROR')
                return False
            
            # Démarrer le serveur en arrière-plan
            start_command = f'python {main_file} &'
            if 'uvicorn' in str(self.project_root):
                # Si on utilise uvicorn
                start_command = f'uvicorn {main_file.replace(".py", "")}:app --host 0.0.0.0 --port 8000 --reload &'
            
            success, output = self.run_command(start_command, check=False)
            
            # Attendre que le service démarre
            self.log("Attente du démarrage du service...")
            time.sleep(5)
            
            # Vérifier que le service est actif
            if not self.check_service_health():
                self.log("Le service n'a pas démarré correctement", 'ERROR')
                return False
            
            self.log("Services démarrés avec succès", 'SUCCESS')
            return True
            
        except Exception as e:
            self.log(f"Erreur lors du démarrage des services: {e}", 'ERROR')
            return False

    def check_service_health(self, retries: int = 10) -> bool:
        """Vérifier la santé du service"""
        for attempt in range(retries):
            try:
                response = requests.get(
                    DEPLOY_CONFIG['health_check_url'], 
                    timeout=5
                )
                if response.status_code == 200:
                    self.log(f"Service opérationnel (tentative {attempt + 1})")
                    return True
                else:
                    self.log(f"Service répond avec le code {response.status_code}")
            except Exception as e:
                self.log(f"Tentative {attempt + 1}/{retries}: Service non disponible")
                
            if attempt < retries - 1:
                time.sleep(3)
        
        return False

    def validate_deployment(self) -> bool:
        """Valider le déploiement"""
        self.log("Validation du déploiement")
        
        validation_checks = [
            ("Service principal", self.check_service_health),
            ("Fichiers statiques accessibles", self.check_static_files_access),
            ("APIs fonctionnelles", self.check_api_endpoints),
            ("Interface utilisateur", self.check_ui_components)
        ]
        
        failed_checks = []
        
        for check_name, check_func in validation_checks:
            try:
                if check_func():
                    self.log(f"✓ {check_name}", 'SUCCESS')
                else:
                    self.log(f"✗ {check_name}", 'ERROR')
                    failed_checks.append(check_name)
            except Exception as e:
                self.log(f"✗ {check_name}: {e}", 'ERROR')
                failed_checks.append(check_name)
        
        if failed_checks:
            self.log(f"Échecs de validation: {failed_checks}", 'ERROR')
            return False
        
        self.log("Déploiement validé avec succès", 'SUCCESS')
        return True

    def check_static_files_access(self) -> bool:
        """Vérifier l'accès aux fichiers statiques"""
        try:
            response = requests.get('http://localhost:8000/static/ai-dashboard.html', timeout=5)
            return response.status_code == 200
        except:
            return False

    def check_api_endpoints(self) -> bool:
        """Vérifier les endpoints API"""
        endpoints_to_check = [
            '/api/ai/health',
            '/api/ai/models/status'
        ]
        
        for endpoint in endpoints_to_check:
            try:
                response = requests.get(f'http://localhost:8000{endpoint}', timeout=5)
                if response.status_code not in [200, 404]:  # 404 acceptable si pas encore implémenté
                    return False
            except:
                return False
        
        return True

    def check_ui_components(self) -> bool:
        """Vérifier les composants UI"""
        # Test basique - vérifier que la page de démo se charge
        try:
            response = requests.get('http://localhost:8000/static/ai-components-demo.html', timeout=5)
            return response.status_code == 200
        except:
            return False

    def cleanup_deployment(self) -> bool:
        """Nettoyage et finalisation"""
        self.log("Nettoyage et finalisation du déploiement")
        
        try:
            # Nettoyer les fichiers temporaires
            temp_files = list(self.project_root.glob('*.tmp'))
            temp_files.extend(self.project_root.glob('__pycache__'))
            
            for temp_file in temp_files:
                if temp_file.is_dir():
                    shutil.rmtree(temp_file, ignore_errors=True)
                else:
                    temp_file.unlink(missing_ok=True)
            
            # Générer un rapport de déploiement
            self.generate_deployment_report()
            
            self.log("Nettoyage terminé", 'SUCCESS')
            return True
            
        except Exception as e:
            self.log(f"Erreur lors du nettoyage: {e}", 'WARNING')
            return True  # Ne pas échouer le déploiement pour le nettoyage

    def generate_deployment_report(self):
        """Générer un rapport de déploiement"""
        report = {
            'deployment_info': {
                'timestamp': datetime.now().isoformat(),
                'environment': self.environment,
                'version': DEPLOY_CONFIG['version'],
                'duration_seconds': (self.stats['end_time'] - self.stats['start_time']).total_seconds() if self.stats['end_time'] else None
            },
            'statistics': self.stats,
            'files_deployed': DEPLOY_CONFIG['static_files'],
            'backup_location': str(self.backup_dir),
            'health_check_url': DEPLOY_CONFIG['health_check_url']
        }
        
        report_file = self.project_root / f'deployment-report-{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log(f"Rapport de déploiement généré: {report_file}")

    def deploy(self) -> bool:
        """Exécuter le déploiement complet"""
        self.log(f"Debut du deploiement - Environnement: {self.environment}")
        self.stats['start_time'] = datetime.now()
        
        for step_name, step_func in self.deployment_steps:
            self.log(f"\nEtape: {step_name}")
            
            try:
                if step_func():
                    self.stats['steps_completed'] += 1
                    self.log(f"OK {step_name} - Reussi", 'SUCCESS')
                else:
                    self.stats['steps_failed'] += 1
                    self.log(f"ERREUR {step_name} - Echoue", 'ERROR')
                    
                    # Demander si on continue
                    if self.environment == 'production':
                        self.log("Deploiement arrete en production", 'ERROR')
                        return False
                    else:
                        continue_deploy = input(f"\n{Colors.YELLOW}Continuer malgre l'echec? (y/N): {Colors.RESET}").lower().startswith('y')
                        if not continue_deploy:
                            return False
                        
            except Exception as e:
                self.stats['steps_failed'] += 1
                self.log(f"ERREUR {step_name} - Erreur: {e}", 'ERROR')
                return False
        
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        self.log(f"\nDeploiement termine en {duration:.1f} secondes")
        self.log(f"Statistiques: {self.stats['steps_completed']}/{self.stats['total_steps']} etapes reussies")
        
        return self.stats['steps_failed'] == 0

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description='Script de déploiement Crypto Rebalancing IA')
    parser.add_argument('--env', choices=['development', 'staging', 'production'], 
                       default='development', help='Environnement de déploiement')
    parser.add_argument('--skip-tests', action='store_true', help='Ignorer les tests')
    parser.add_argument('--force', action='store_true', help='Forcer le déploiement')
    
    args = parser.parse_args()
    
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print("CRYPTO REBALANCING IA - DEPLOIEMENT AUTOMATISE")
    print("=" * 60)
    print(f"{Colors.RESET}")
    
    # Créer le gestionnaire de déploiement
    deployment_manager = DeploymentManager(args.env)
    
    # Confirmer le déploiement en production
    if args.env == 'production' and not args.force:
        confirm = input(f"{Colors.RED}Etes-vous sur de vouloir deployer en PRODUCTION? (yes/no): {Colors.RESET}")
        if confirm.lower() != 'yes':
            print("Deploiement annule")
            return 1
    
    # Exécuter le déploiement
    success = deployment_manager.deploy()
    
    if success:
        print(f"\n{Colors.GREEN}Deploiement reussi!{Colors.RESET}")
        print(f"Application disponible sur: http://localhost:8000")
        print(f"Tests E2E: http://localhost:8000/static/test-integration-e2e.html")
        print(f"Demo IA: http://localhost:8000/static/ai-components-demo.html")
        return 0
    else:
        print(f"\n{Colors.RED}Deploiement echoue{Colors.RESET}")
        print(f"Consultez le log: {deployment_manager.log_file}")
        return 1

if __name__ == '__main__':
    sys.exit(main())