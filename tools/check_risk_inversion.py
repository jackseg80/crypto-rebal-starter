#!/usr/bin/env python3
"""
Hook pre-commit pour détecter les inversions de Risk Score.

Le Risk Score est défini comme positif [0..100] où plus haut = plus robuste.
Cette règle canonique est documentée dans docs/RISK_SEMANTICS.md.

Ce hook détecte les patterns interdits comme:
- 100 - risk
- 100 - scoreRisk
- 100 - riskScore

Usage:
    python tools/check_risk_inversion.py file1.py file2.js ...
"""
import re
import sys
import io
import os

PATTERNS = [
    r'100\s*-\s*risk\b',
    r'100\s*-\s*scoreRisk\b',
    r'100\s*-\s*riskScore\b',
    r'\b(100|100\.0)\s*-\s*(risk|scoreRisk|riskScore)\b',
]

def check_file(path):
    """Check a single file for Risk inversion patterns."""
    try:
        with io.open(path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    except Exception as e:
        return None  # ignore unreadable files

    for pat in PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return f"❌ {path}: Risk inversion détectée (pattern: `{pat}`)"
    return None

def main(args):
    """Main entry point."""
    errors = []
    for p in args[1:]:
        if not os.path.isfile(p):
            continue
        if any(p.endswith(ext) for ext in ('.py', '.js', '.ts', '.tsx')):
            e = check_file(p)
            if e:
                errors.append(e)

    if errors:
        print("\n".join(errors))
        print("\n💡 Voir docs/RISK_SEMANTICS.md — Risk ∈ [0..100], plus haut = plus robuste ; ne jamais faire `100 - risk`.")
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)
