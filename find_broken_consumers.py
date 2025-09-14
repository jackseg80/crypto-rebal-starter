#!/usr/bin/env python3
"""
Script pour identifier les consumers frontend qui utilisent les anciennes routes
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Set

# Routes supprimées à vérifier
REMOVED_ROUTES = [
    "/api/ml-predictions",
    "/api/test/risk",
    "/api/alerts/test",
    "/api/realtime/publish",
    "/api/realtime/broadcast",
    "/governance/approve\"",  # Ancien endpoint sans paramètre
    "/api/advanced-risk",  # Ancien namespace
]

# Routes modifiées à vérifier
MODIFIED_ROUTES = [
    "/governance/approve/",  # Maintenant unifié avec resource_id
    "/api/risk/alerts/",     # Maintenant centralisé sous /api/alerts/
]

def find_files_with_extension(directory: str, extensions: List[str]) -> List[Path]:
    """Trouve tous les fichiers avec les extensions spécifiées"""
    files = []
    for ext in extensions:
        files.extend(Path(directory).rglob(f"*.{ext}"))
    return files

def search_in_file(file_path: Path, patterns: List[str]) -> Dict[str, List[int]]:
    """Cherche les patterns dans un fichier et retourne les numéros de ligne"""
    matches = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for pattern in patterns:
            pattern_matches = []
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    pattern_matches.append(i)
            
            if pattern_matches:
                matches[pattern] = pattern_matches
                
    except Exception as e:
        print(f"WARNING: Error reading {file_path}: {e}")
    
    return matches

def main():
    print("Scanning for broken consumers after endpoint refactoring...\n")
    
    # Répertoires à scanner
    directories_to_scan = [
        "static",
        "tests",
        "scripts",
        "docs"
    ]
    
    # Extensions de fichiers à vérifier
    extensions = ["html", "js", "ts", "py", "md", "json", "yaml", "yml"]
    
    all_patterns = REMOVED_ROUTES + MODIFIED_ROUTES
    broken_consumers = {}
    
    for directory in directories_to_scan:
        if not os.path.exists(directory):
            continue
            
        print(f"Scanning {directory}...")
        files = find_files_with_extension(directory, extensions)
        
        for file_path in files:
            matches = search_in_file(file_path, all_patterns)
            if matches:
                broken_consumers[str(file_path)] = matches
    
    # Rapport
    print(f"\n{'='*60}")
    print("SCAN RESULTS")
    print(f"{'='*60}")
    
    if not broken_consumers:
        print("OK: No references to old endpoints found!")
        return 0
    
    print(f"ALERT: Found {len(broken_consumers)} files with references to old endpoints:")
    print()
    
    # Grouper par type de problème
    removed_refs = {}
    modified_refs = {}
    
    for file_path, matches in broken_consumers.items():
        for pattern, lines in matches.items():
            if pattern in REMOVED_ROUTES:
                if pattern not in removed_refs:
                    removed_refs[pattern] = []
                removed_refs[pattern].append((file_path, lines))
            else:
                if pattern not in modified_refs:
                    modified_refs[pattern] = []
                modified_refs[pattern].append((file_path, lines))
    
    # Références aux endpoints supprimés
    if removed_refs:
        print("REMOVED ENDPOINTS (need immediate fix):")
        for pattern, file_refs in removed_refs.items():
            print(f"\n  Route: {pattern}")
            for file_path, lines in file_refs:
                print(f"     {file_path}:{lines}")
    
    # Références aux endpoints modifiés  
    if modified_refs:
        print("\nMODIFIED ENDPOINTS (may need updates):")
        for pattern, file_refs in modified_refs.items():
            print(f"\n  Route: {pattern}")
            for file_path, lines in file_refs:
                print(f"     {file_path}:{lines}")
    
    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")
    
    print("\nFor REMOVED endpoints:")
    print("  - /api/ml-predictions -> /api/ml")
    print("  - /api/test/* -> Remove all test calls")
    print("  - /api/alerts/test/* -> Remove all test calls")  
    print("  - /api/realtime/publish,broadcast -> Remove (security)")
    print("  - /api/advanced-risk -> /api/risk/advanced")
    
    print("\nFor MODIFIED endpoints:")
    print("  - /governance/approve -> /governance/approve/{resource_id}")
    print("    (add resource_type: 'decision'|'plan' in body)")
    print("  - /api/*/alerts/{id}/resolve -> /api/alerts/resolve/{id}")
    
    return 1 if broken_consumers else 0

if __name__ == "__main__":
    sys.exit(main())