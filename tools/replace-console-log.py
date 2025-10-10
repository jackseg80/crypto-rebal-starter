#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de remplacement automatique console.log → debugLogger
Pour nettoyer le code production et utiliser le système de logging centralisé

Usage:
    python tools/replace-console-log.py --dry-run    # Voir les changements sans appliquer
    python tools/replace-console-log.py --apply      # Appliquer les changements
    python tools/replace-console-log.py --file dashboard.html  # Un fichier spécifique
"""

import os
import re
import argparse
import json
from pathlib import Path
from typing import List, Dict, Tuple

# Configuration
STATIC_DIR = Path("static")
EXCLUDED_PATTERNS = [
    "archive/",
    "debug/",
    "tests/",
    "test-",
    "debug-logger.js",  # Ne pas modifier le logger lui-même
]

# Patterns de remplacement
REPLACEMENTS = [
    # console.log() → debugLogger.debug()
    (r'\bconsole\.log\(', 'debugLogger.debug('),

    # console.warn() → debugLogger.warn()
    (r'\bconsole\.warn\(', 'debugLogger.warn('),

    # console.error() → debugLogger.error()
    (r'\bconsole\.error\(', 'debugLogger.error('),

    # console.info() → debugLogger.info()
    (r'\bconsole\.info\(', 'debugLogger.info('),

    # Note: console.debug() est laissé tel quel (géré par hooks dans debug-logger.js)
]


def should_exclude(file_path: Path) -> bool:
    """Vérifie si le fichier doit être exclu"""
    path_str = str(file_path).replace('\\', '/')
    return any(pattern in path_str for pattern in EXCLUDED_PATTERNS)


def find_files_to_process() -> List[Path]:
    """Trouve tous les fichiers JS/HTML à traiter"""
    files = []

    for ext in ['*.js', '*.html']:
        for file_path in STATIC_DIR.rglob(ext):
            if not should_exclude(file_path):
                files.append(file_path)

    return sorted(files)


def count_console_calls(content: str) -> Dict[str, int]:
    """Compte les différents types d'appels console"""
    counts = {
        'log': len(re.findall(r'\bconsole\.log\(', content)),
        'warn': len(re.findall(r'\bconsole\.warn\(', content)),
        'error': len(re.findall(r'\bconsole\.error\(', content)),
        'info': len(re.findall(r'\bconsole\.info\(', content)),
        'debug': len(re.findall(r'\bconsole\.debug\(', content)),
    }
    return {k: v for k, v in counts.items() if v > 0}


def apply_replacements(content: str) -> Tuple[str, int]:
    """Applique les remplacements et retourne (nouveau_contenu, nombre_changements)"""
    new_content = content
    total_changes = 0

    for pattern, replacement in REPLACEMENTS:
        matches = len(re.findall(pattern, new_content))
        if matches > 0:
            new_content = re.sub(pattern, replacement, new_content)
            total_changes += matches

    return new_content, total_changes


def process_file(file_path: Path, dry_run: bool = True) -> Dict:
    """Traite un fichier et retourne un rapport"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        return {
            'file': str(file_path),
            'status': 'error',
            'error': str(e)
        }

    # Compter avant
    console_calls_before = count_console_calls(original_content)

    if not console_calls_before:
        return {
            'file': str(file_path),
            'status': 'skipped',
            'reason': 'no console calls'
        }

    # Appliquer remplacements
    new_content, changes_count = apply_replacements(original_content)

    if changes_count == 0:
        return {
            'file': str(file_path),
            'status': 'skipped',
            'reason': 'only console.debug (already handled by hooks)',
            'console_calls': console_calls_before
        }

    # Compter après
    console_calls_after = count_console_calls(new_content)

    # Écrire le fichier si pas en dry-run
    if not dry_run:
        # Créer backup
        backup_path = file_path.with_suffix(file_path.suffix + '.backup')
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
        except Exception as e:
            return {
                'file': str(file_path),
                'status': 'error',
                'error': f'Backup failed: {e}'
            }

        # Écrire nouveau contenu
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            # Restaurer backup
            with open(backup_path, 'r', encoding='utf-8') as f:
                original = f.read()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(original)
            return {
                'file': str(file_path),
                'status': 'error',
                'error': f'Write failed: {e}'
            }

    return {
        'file': str(file_path),
        'status': 'modified' if not dry_run else 'would_modify',
        'changes_count': changes_count,
        'console_calls_before': console_calls_before,
        'console_calls_after': console_calls_after
    }


def main():
    parser = argparse.ArgumentParser(description='Replace console.log with debugLogger')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be changed without applying (default)')
    parser.add_argument('--apply', action='store_true',
                       help='Actually apply the changes')
    parser.add_argument('--file', type=str,
                       help='Process only this specific file (relative to static/)')
    parser.add_argument('--report', type=str,
                       help='Save report to JSON file')

    args = parser.parse_args()

    dry_run = not args.apply

    # Trouver fichiers à traiter
    if args.file:
        files = [STATIC_DIR / args.file]
    else:
        files = find_files_to_process()

    mode_text = "DRY-RUN MODE (preview only)" if dry_run else "APPLY MODE (changes will be made)"
    print(f"\n{'='*60}")
    print(f"{mode_text}")
    print(f"{'='*60}")
    print(f"Found {len(files)} files to process")
    print()

    # Traiter les fichiers
    results = []
    stats = {
        'total_files': len(files),
        'modified': 0,
        'skipped': 0,
        'errors': 0,
        'total_changes': 0
    }

    for file_path in files:
        result = process_file(file_path, dry_run=dry_run)
        results.append(result)

        if result['status'] in ['modified', 'would_modify']:
            stats['modified'] += 1
            stats['total_changes'] += result.get('changes_count', 0)

            # Afficher détails
            rel_path = file_path.relative_to(STATIC_DIR)
            prefix = "[APPLY]" if not dry_run else "[PREVIEW]"
            print(f"{prefix} {rel_path}")
            print(f"   Changes: {result['changes_count']}")
            print(f"   Before: {result['console_calls_before']}")
            print(f"   After:  {result['console_calls_after']}")
            print()
        elif result['status'] == 'error':
            stats['errors'] += 1
            print(f"[ERROR] {file_path}: {result.get('error')}")
        else:
            stats['skipped'] += 1

    # Résumé
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files scanned: {stats['total_files']}")
    print(f"{'Would be modified' if dry_run else 'Modified'}: {stats['modified']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    print(f"Total replacements: {stats['total_changes']}")
    print()

    if dry_run:
        print("[INFO] This was a DRY-RUN. No files were modified.")
        print("       Run with --apply to actually make changes.")
    else:
        print("[SUCCESS] Changes applied successfully!")
        print("          Backup files created with .backup extension")

    # Sauvegarder rapport JSON si demandé
    if args.report:
        report_data = {
            'stats': stats,
            'results': results,
            'dry_run': dry_run
        }
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"\n[REPORT] Saved to: {args.report}")


if __name__ == '__main__':
    main()
