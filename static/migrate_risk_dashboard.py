#!/usr/bin/env python3
"""
Script to migrate risk-dashboard.html to use external modules
This script:
1. Replaces inline CSS with external stylesheet link
2. Adds orchestrator module import
3. Creates a backup of the original file
"""

import re
from pathlib import Path
from datetime import datetime

def migrate_risk_dashboard():
    """Apply all migrations to risk-dashboard.html"""

    # Paths
    html_file = Path(__file__).parent / 'risk-dashboard.html'
    backup_file = Path(__file__).parent / f'risk-dashboard.html.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'

    print(f"[1/5] Reading {html_file}")

    # Read original file
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    original_lines = content.count('\n')
    print(f"      Original file: {original_lines} lines")

    # Backup original
    print(f"[2/5] Creating backup at {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)

    # ===== Modification 1: Replace inline CSS with external link =====
    print("[3/5] Replacing inline CSS with external stylesheet...")

    # Find the <style> block (from line 39 to line 1928)
    css_pattern = r'  <style>\s*\n.*?  </style>\s*\n'
    css_replacement = '  <!-- Risk Dashboard CSS -->\n  <link rel="stylesheet" href="css/risk-dashboard.css">\n\n'

    content_new = re.sub(css_pattern, css_replacement, content, flags=re.DOTALL)

    if content_new == content:
        print("      WARNING: CSS block not replaced (pattern might need adjustment)")
    else:
        print("      SUCCESS: CSS block replaced")
        css_removed = content.count('\n') - content_new.count('\n')
        print(f"      Removed ~{css_removed} lines of inline CSS")

    content = content_new

    # ===== Modification 2: Add orchestrator import =====
    print("[4/5] Adding orchestrator module import...")

    # Find the line with tooltips.js and add orchestrator after it
    tooltips_pattern = r'(<script type="module" src="components/tooltips\.js"></script>\s*\n)(</head>)'
    orchestrator_addition = r'\1\n  <!-- Risk Dashboard Orchestrator -->\n  <script type="module" src="modules/risk-dashboard-main.js"></script>\n\2'

    content_new = re.sub(tooltips_pattern, orchestrator_addition, content)

    if content_new == content:
        print("      WARNING: Orchestrator import not added (pattern might need adjustment)")
    else:
        print("      SUCCESS: Orchestrator import added")

    content = content_new

    # ===== Write modified file =====
    print(f"[5/5] Writing modified file to {html_file}")

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(content)

    new_lines = content.count('\n')
    reduction = original_lines - new_lines

    print(f"\n=== Migration Completed Successfully ===")
    print(f"New file: {new_lines} lines")
    print(f"Reduction: {reduction} lines ({reduction/original_lines*100:.1f}%)")
    print(f"\nBackup saved at: {backup_file}")
    print(f"\nNext steps:")
    print(f"   1. Open http://localhost:8000/static/risk-dashboard.html")
    print(f"   2. Check browser console for module loading")
    print(f"   3. Test tab switching (especially Alerts tab)")
    print(f"   4. If issues occur, restore from backup")

if __name__ == '__main__':
    try:
        migrate_risk_dashboard()
    except Exception as e:
        print(f"ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
