#!/usr/bin/env python3
"""
gen_broken_refs.py — Détecteur de références cassées dans la documentation

Scanne tous les fichiers markdown pour :
- Liens internes markdown [text](path)
- Références à des fichiers
- Vérifie l'existence des fichiers référencés

Génère : broken_refs_raw.csv
"""

import re
import csv
from pathlib import Path
from typing import List, Dict, Tuple

def extract_markdown_links(filepath: Path) -> List[Tuple[int, str, str, str]]:
    """
    Extrait tous les liens markdown d'un fichier
    Returns: List[(line_num, link_text, link_path, context_snippet)]
    """
    links = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines, start=1):
            # Pattern markdown [text](path)
            matches = re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', line)

            for match in matches:
                link_text = match.group(1)
                link_path = match.group(2)

                # Ignorer URLs externes
                if link_path.startswith(('http://', 'https://', '#', 'mailto:')):
                    continue

                # Contexte (40 chars autour)
                start = max(0, match.start() - 20)
                end = min(len(line), match.end() + 20)
                context = line[start:end].strip()

                links.append((i, link_text, link_path, context))

    except Exception as e:
        print(f"[!] Erreur lecture {filepath}: {e}")

    return links

def check_file_exists(base_path: Path, ref_path: str) -> bool:
    """
    Vérifie si un fichier référencé existe
    Gère les chemins relatifs, absolus, et les anchors (#section)
    """
    # Retirer les anchors (#section)
    clean_path = ref_path.split('#')[0]

    if not clean_path:
        return True  # Anchor vers même fichier

    # Construire chemin complet
    if clean_path.startswith('/'):
        # Chemin absolu depuis racine projet
        full_path = Path.cwd() / clean_path.lstrip('/')
    else:
        # Chemin relatif depuis base_path
        full_path = base_path.parent / clean_path

    # Normaliser et vérifier
    try:
        full_path = full_path.resolve()
        return full_path.exists()
    except Exception:
        return False

def prioritize_doc(filepath: Path) -> str:
    """
    Détermine la priorité d'un document
    Returns: HIGH, MEDIUM, LOW, IGNORE
    """
    name = filepath.name.lower()
    path_str = str(filepath).lower()

    # IGNORE
    if 'data/logs' in path_str or filepath.suffix == '.txt':
        return 'IGNORE'

    # HIGH : docs racine
    if filepath.parent == Path.cwd() and filepath.suffix == '.md':
        return 'HIGH'

    # LOW : archive/legacy
    if '_archive' in path_str or '_legacy' in path_str:
        return 'LOW'

    # MEDIUM : docs techniques
    if 'docs/' in path_str:
        return 'MEDIUM'

    return 'MEDIUM'

def main():
    """Point d'entrée principal"""
    print("[*] Scanning markdown files...")

    # Trouver tous les fichiers markdown
    md_files = list(Path.cwd().rglob('*.md'))
    print(f"[+] Found {len(md_files)} markdown files")

    # Extraire liens et vérifier
    broken_refs = []
    total_links = 0

    for md_file in md_files:
        links = extract_markdown_links(md_file)
        total_links += len(links)

        for line_num, link_text, link_path, context in links:
            if not check_file_exists(md_file, link_path):
                priority = prioritize_doc(md_file)

                broken_refs.append({
                    'doc': str(md_file.relative_to(Path.cwd())),
                    'line': line_num,
                    'link_text': link_text,
                    'missing_path': link_path,
                    'context_snippet': context,
                    'priority': priority
                })

    print(f"[+] Checked {total_links} links")
    print(f"[!] Found {len(broken_refs)} broken references")

    # Grouper par priorité
    by_priority = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'IGNORE': 0}
    for ref in broken_refs:
        by_priority[ref['priority']] += 1

    print(f"[+] Breakdown: HIGH={by_priority['HIGH']}, MEDIUM={by_priority['MEDIUM']}, LOW={by_priority['LOW']}, IGNORE={by_priority['IGNORE']}")

    # Générer CSV
    output_path = Path('broken_refs_raw.csv')

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['doc', 'line', 'link_text', 'missing_path', 'context_snippet', 'priority'])
        writer.writeheader()
        writer.writerows(broken_refs)

    print(f"[+] Generated: {output_path}")

    # Top 20 docs avec le plus de refs cassées
    from collections import Counter
    top_docs = Counter(ref['doc'] for ref in broken_refs).most_common(20)

    print("\n[*] Top 20 docs with broken refs:")
    for doc, count in top_docs:
        print(f"  {count:3d} - {doc}")

if __name__ == "__main__":
    main()
