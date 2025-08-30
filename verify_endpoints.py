#!/usr/bin/env python3
from api.main import app

print("VERIFICATION DES ENDPOINTS AJOUTES")
print("=" * 40)

# Lister toutes les routes
routes = []
for route in app.routes:
    if hasattr(route, 'path'):
        routes.append(route.path)

# Rechercher nos nouveaux endpoints
health_routes = [r for r in routes if 'health' in r.lower()]
pricing_routes = [r for r in routes if 'pricing' in r.lower()]

print(f"Total routes: {len(routes)}")
print(f"\nRoutes health:")
for r in health_routes:
    print(f"  {r}")

print(f"\nRoutes pricing:")
for r in pricing_routes:
    print(f"  {r}")

# Vérifications
has_health_detailed = '/health/detailed' in routes
has_pricing_diagnostic = '/pricing/diagnostic' in routes

print(f"\nVERIFICATIONS:")
print(f"/health/detailed: {'PRESENT' if has_health_detailed else 'ABSENT'}")
print(f"/pricing/diagnostic: {'PRESENT' if has_pricing_diagnostic else 'ABSENT'}")

if has_health_detailed and has_pricing_diagnostic:
    print(f"\nCONCLUSION: Les endpoints sont correctement definis dans le code.")
    print("Si ils n'apparaissent pas dans /docs, redemarrez le serveur:")
    print("uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload")
else:
    print(f"\nPROBLEME: Certains endpoints manquent dans la definition.")