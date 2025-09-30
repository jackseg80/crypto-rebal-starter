#!/usr/bin/env python3
"""
Script de validation sécuritaire - Crypto Rebalancer
Usage: python tools/security-check.py
"""

import os
import re
import json
from pathlib import Path

def check_env_files():
    """Vérifie les fichiers d'environnement"""
    errors = []
    warnings = []

    # .env ne doit pas être commité
    if os.path.exists('.env'):
        errors.append(".env file found in repository!")
    else:
        print("OK No .env file in repository")

    # .env.example doit exister et être propre
    if os.path.exists('.env.example'):
        with open('.env.example', 'r', encoding='utf-8') as f:
            content = f.read()

        # Chercher des patterns de vraies clés
        if re.search(r'[A-Za-z0-9]{20,}', content):
            warnings.append(".env.example might contain actual secrets")
        else:
            print("OK .env.example appears clean")

    return errors, warnings

def check_console_logs():
    """Compte les console.log restants"""
    static_dir = Path('static')
    if not static_dir.exists():
        return 0

    count = 0
    for js_file in static_dir.rglob('*.js'):
        if '.min.' in js_file.name:
            continue

        try:
            content = js_file.read_text(encoding='utf-8')
            matches = len(re.findall(r'console\.log\(', content))
            count += matches
        except Exception:
            pass

    return count

def check_secrets_in_code():
    """Scan basique pour secrets évidents"""
    suspicious_files = []

    patterns = [
        r'api_key\s*=\s*["\'][A-Za-z0-9]{15,}["\']',
        r'secret\s*=\s*["\'][A-Za-z0-9]{15,}["\']',
        r'token\s*=\s*["\'][A-Za-z0-9]{20,}["\']'
    ]

    for ext in ['*.py', '*.js']:
        for file_path in Path('.').rglob(ext):
            if 'test' in file_path.name.lower() or 'example' in file_path.name.lower():
                continue

            try:
                content = file_path.read_text(encoding='utf-8')
                for pattern in patterns:
                    if re.search(pattern, content):
                        suspicious_files.append(file_path.name)
                        break
            except Exception:
                pass

    return suspicious_files

def check_config_files():
    """Vérifie les fichiers de configuration sécuritaire"""
    checks = {}

    # ESLint
    if os.path.exists('.eslintrc.json'):
        try:
            with open('.eslintrc.json', 'r', encoding='utf-8') as f:
                eslint = json.load(f)

            rules = eslint.get('rules', {})
            checks['eslint'] = (
                'no-console' in rules and 'no-eval' in rules
            )
        except Exception:
            checks['eslint'] = False
    else:
        checks['eslint'] = False

    # Pre-commit
    if os.path.exists('.pre-commit-config.yaml'):
        try:
            with open('.pre-commit-config.yaml', 'r', encoding='utf-8') as f:
                content = f.read()

            checks['precommit'] = (
                'gitleaks' in content and 'detect-secrets' in content
            )
        except Exception:
            checks['precommit'] = False
    else:
        checks['precommit'] = False

    # Security tests
    checks['security_tests'] = os.path.exists('tests/test_security_headers.py')

    return checks

def main():
    print("Security Check - Crypto Rebalancer")
    print("=" * 40)

    errors = []
    warnings = []

    # 1. Fichiers d'environnement
    print("\n1. Environment files...")
    env_errors, env_warnings = check_env_files()
    errors.extend(env_errors)
    warnings.extend(env_warnings)

    # 2. Console.log
    print("\n2. Console.log usage...")
    console_count = check_console_logs()
    if console_count == 0:
        print("OK No console.log found")
    elif console_count < 50:
        print(f"WARNING {console_count} console.log found (acceptable)")
        warnings.append(f"{console_count} console.log remaining")
    else:
        print(f"ERROR {console_count} console.log found (too many)")
        errors.append(f"Too many console.log: {console_count}")

    # 3. Secrets dans le code
    print("\n3. Secrets in code...")
    suspicious = check_secrets_in_code()
    if not suspicious:
        print("OK No obvious secrets found")
    else:
        print(f"WARNING {len(suspicious)} files with potential secrets")
        warnings.extend([f"Potential secret in {f}" for f in suspicious])

    # 4. Configuration files
    print("\n4. Security configuration...")
    configs = check_config_files()

    if configs['eslint']:
        print("OK ESLint configured with security rules")
    else:
        print("ERROR ESLint missing or incomplete")
        errors.append("ESLint security rules missing")

    if configs['precommit']:
        print("OK Pre-commit hooks configured")
    else:
        print("ERROR Pre-commit hooks missing or incomplete")
        errors.append("Pre-commit hooks missing")

    if configs['security_tests']:
        print("OK Security tests present")
    else:
        print("ERROR Security tests missing")
        errors.append("Security tests missing")

    # Résumé
    print("\n" + "=" * 40)
    print("SECURITY CHECK SUMMARY")
    print("=" * 40)

    if not errors and not warnings:
        print("Perfect security score!")
        return 0
    elif not errors:
        print(f"Good security posture. {len(warnings)} warning(s):")
        for w in warnings[:5]:  # Limite à 5 warnings
            print(f"  WARNING: {w}")
        return 0
    else:
        print(f"Security issues: {len(errors)} error(s), {len(warnings)} warning(s)")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())