#!/usr/bin/env python3
"""
gen_api_reference.py — Générateur automatique de documentation API (v2)

Scanne tous les fichiers Python dans api/ pour extraire :
- Routes FastAPI (@app.get, @router.post, etc.)
- Prefixes APIRouter
- Docstrings et paramètres
- Tags

Génère : docs/API_REFERENCE.md avec groupement par namespace
"""

import re
import os
import glob

DECOS = ("get", "post", "put", "delete", "patch")
ROUTER_DECL_RE = re.compile(r"APIRouter\s*\((?P<args>.*?)\)", re.S)
PREFIX_KV_RE = re.compile(r"prefix\s*=\s*['\"](?P<prefix>[^'\"]+)['\"]")
INCLUDE_ROUTER_RE = re.compile(r"\.include_router\s*\(\s*(?P<router_var>[A-Za-z0-9_]+)\s*(?:,|\))(?P<rest>.*?)\)", re.S)
INCLUDE_PREFIX_RE = re.compile(r"prefix\s*=\s*['\"](?P<prefix>[^'\"]+)['\"]")
ROUTE_RE = re.compile(r"@(?P<obj>app|router)\.(?P<meth>" + "|".join(DECOS) + r")\s*\(\s*['\"](?P<path>[^'\"]+)['\"](?P<rest>.*?)\)", re.S)

DEF_RE = re.compile(r"def\s+(?P<name>[A-Za-z0-9_]+)\s*\(")
DOCSTR_RE = re.compile(r'^\s*[ru]?["\']{3}(.+?)["\']{3}', re.S | re.M)
TAGS_RE = re.compile(r"tags\s*=\s*\[([^\]]+)\]")


def read(path):
    """Lit un fichier avec gestion d'erreurs"""
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def find_router_prefixes(text):
    """Trouve les déclarations router = APIRouter(prefix="/...")"""
    prefixes = {}
    for m in re.finditer(r"(?P<var>[A-Za-z0-9_]+)\s*=\s*" + ROUTER_DECL_RE.pattern, text, re.S):
        var = m.group("var")
        args = m.group("args")
        pm = PREFIX_KV_RE.search(args or "")
        if pm:
            prefixes[var] = pm.group("prefix")
    return prefixes


def find_include_prefixes(text, router_prefixes):
    """Trouve les app.include_router(router, prefix="/...")"""
    extra = []
    for m in INCLUDE_ROUTER_RE.finditer(text):
        var = m.group("router_var")
        rest = m.group("rest") or ""
        pm = INCLUDE_PREFIX_RE.search(rest)
        pref = pm.group("prefix") if pm else ""
        base = router_prefixes.get(var, "")
        full = (base or "") + (pref or "")
        extra.append((var, full))
    return dict(extra)


def first_def_docstring(block):
    """Extrait la première ligne de docstring après un def"""
    dm = DEF_RE.search(block)
    if not dm:
        return ""
    tail = block[dm.end():]
    m = DOCSTR_RE.search(tail)
    if not m:
        return ""
    doc = m.group(1).strip()
    return doc.splitlines()[0].strip() if doc else ""


def extract_routes(path):
    """Extrait toutes les routes d'un fichier Python"""
    txt = read(path)
    if not txt:
        return []

    routes = []
    router_prefixes = find_router_prefixes(txt)

    for m in ROUTE_RE.finditer(txt):
        obj = m.group("obj")  # app|router
        method = m.group("meth").upper()
        route = m.group("path")
        rest = m.group("rest") or ""

        # Tags (optional)
        tags = ""
        t = TAGS_RE.search(rest)
        if t:
            tags = re.sub(r"[\s'\"]", "", t.group(1))

        # Local prefix (router prefix in this file)
        local_prefix = ""
        if obj == "router":
            # Heuristic: choose first router prefix if any
            if router_prefixes:
                local_prefix = list(router_prefixes.values())[0]

        full_path = (local_prefix or "") + route
        # Normalize slashes
        full_path = re.sub(r"//+", "/", full_path)

        # Docstring summary
        start = m.end()
        snippet = txt[start:start + 1200]
        summary = first_def_docstring(snippet)

        routes.append({
            "file": os.path.relpath(path, os.getcwd()).replace("\\", "/"),
            "method": method,
            "path": full_path if full_path.startswith("/") else "/" + full_path,
            "tags": tags,
            "summary": summary
        })
    return routes


def main():
    """Point d'entrée principal"""
    print("[*] Scanning API files...")

    # Scanner tous les fichiers Python dans api/
    files = glob.glob("api/**/*.py", recursive=True)
    files.extend(glob.glob("api/*.py"))

    print(f"[+] Found {len(files)} Python files")

    # Extraire routes
    routes = []
    for f in files:
        try:
            extracted = extract_routes(f)
            routes.extend(extracted)
        except Exception as e:
            print(f"[!] Error parsing {f}: {e}")

    print(f"[+] Extracted {len(routes)} routes")

    # Dédupliquer
    seen = set()
    unique = []
    for r in routes:
        key = (r["method"], r["path"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    print(f"[+] {len(unique)} unique routes after deduplication")

    # Grouper par namespace
    def ns_of(p):
        if not p.startswith("/"):
            p = "/" + p
        parts = p.strip("/").split("/")
        return ("/" + parts[0]) if parts else "/"

    groups = {}
    for r in unique:
        ns = ns_of(r["path"])
        groups.setdefault(ns, []).append(r)

    print(f"[+] {len(groups)} namespaces")

    # Build markdown
    lines = [
        "# API Reference (auto-généré)",
        "",
        "_Généré par `tools/gen_api_reference.py` — ne pas éditer à la main._",
        "",
        f"**Total endpoints** : {len(unique)}",
        "",
        "## Conventions",
        "- Méthodes triées par chemin",
        "- Groupement par **namespace** (1er segment)",
        "- `summary` = 1ère ligne de docstring si disponible",
        ""
    ]

    for ns in sorted(groups.keys()):
        lines.append(f"## Namespace `{ns}`")
        lines.append("")
        lines.append("| Method | Path | Summary | File |")
        lines.append("|---|---|---|---|")

        for r in sorted(groups[ns], key=lambda x: (x["path"], x["method"])):
            summary = r["summary"][:80] + "..." if len(r["summary"]) > 80 else r["summary"]
            lines.append(f"| {r['method']} | `{r['path']}` | {summary} | `{r['file']}` |")

        lines.append("")

    # Écrire fichier
    os.makedirs("docs", exist_ok=True)
    output_path = "docs/API_REFERENCE.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[+] Generated: {output_path}")
    print(f"[+] {len(unique)} endpoints in {len(groups)} namespaces")


if __name__ == "__main__":
    main()
