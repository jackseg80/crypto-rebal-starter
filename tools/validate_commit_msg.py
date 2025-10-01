#!/usr/bin/env python3
"""
Hook pre-commit pour valider les messages de commit.

Enforce:
- Conventional Commits format: feat|fix|docs|chore|refactor|test|perf|ci(scope): description
- Interdit les messages contenant "WIP" (Work In Progress)
- Limite la première ligne à 72 caractères

Référence: GUIDE_IA.md Section 0 - Politique de Workflow

Usage:
    python tools/validate_commit_msg.py .git/COMMIT_EDITMSG
"""
import re
import sys
import io

# Conventional commits minimal + interdiction WIP
ALLOWED_TYPES = r"(feat|fix|docs|chore|refactor|test|perf|ci)"
FIRST_LINE_RE = re.compile(rf"^{ALLOWED_TYPES}(?:\([^)]+\))?:\s+\S.+$")
FORBIDDEN = re.compile(r"\bWIP\b", re.IGNORECASE)

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("❌ Usage: validate_commit_msg.py <COMMIT_MSG_FILE>")
        sys.exit(1)

    path = sys.argv[1]
    with io.open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.rstrip("\n") for l in f]

    first = lines[0] if lines else ""

    # Check for WIP
    if FORBIDDEN.search(first):
        print("❌ Commit message interdit: contient 'WIP'. Utiliser un message final (voir GUIDE_IA.md Section 0).")
        sys.exit(1)

    # Check Conventional Commits format
    if not FIRST_LINE_RE.match(first):
        print("❌ Format attendu (Conventional Commits):")
        print("   feat|fix|docs|chore|refactor|test|perf|ci(scope): courte description")
        print("\nExemples:")
        print("   feat(simulation): aligner caps journaliers avec prod")
        print("   fix(risk): corriger propagation user_id dans /api/risk/*")
        print("   docs(guide): ajouter section workflow IA")
        sys.exit(1)

    # Check length (≤ 72 recommended)
    if len(first) > 72:
        print(f"❌ Ligne 1 trop longue ({len(first)} char). Viser ≤ 72.")
        sys.exit(1)

    # All checks passed
    sys.exit(0)

if __name__ == "__main__":
    main()
