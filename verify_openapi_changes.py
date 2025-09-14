#!/usr/bin/env python3
"""
Script pour vérifier les changements OpenAPI et identifier les breaking changes
"""

import json
import sys
from typing import Dict, List, Set, Any

def extract_endpoints_from_spec(spec: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    """Extrait tous les endpoints de la spec OpenAPI"""
    endpoints = {}
    
    if 'paths' not in spec:
        return endpoints
    
    for path, methods in spec['paths'].items():
        endpoints[path] = {}
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                endpoints[path][method.upper()] = details.get('tags', [])
    
    return endpoints

def identify_breaking_changes(endpoints: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    """Identifie les breaking changes potentiels"""
    
    # Routes qui ont été supprimées
    removed_routes = [
        "/api/ml-predictions",
        "/api/test/risk", 
        "/api/alerts/test",
        "/api/realtime/publish",
        "/api/realtime/broadcast",
        "/api/advanced-risk"  # Déplacé vers /api/risk/advanced
    ]
    
    # Routes qui ont été modifiées
    modified_routes = {
        "/governance/approve": "Maintenant /governance/approve/{resource_id} avec resource_type dans le body",
        "/api/risk/alerts/{alert_id}/resolve": "Maintenant centralisé sous /api/alerts/resolve/{alert_id}",
        "/api/monitoring/alerts/{alert_id}/resolve": "Maintenant centralisé sous /api/alerts/resolve/{alert_id}",
        "/api/portfolio/alerts/{alert_id}/resolve": "Maintenant centralisé sous /api/alerts/resolve/{alert_id}"
    }
    
    breaking_changes = {
        "removed": [],
        "modified": [],
        "new_unified": [],
        "namespace_changes": []
    }
    
    # Vérifier les routes supprimées
    for removed_route in removed_routes:
        for path in endpoints:
            if removed_route in path:
                breaking_changes["removed"].append(path)
    
    # Vérifier les routes modifiées  
    for modified_route, description in modified_routes.items():
        for path in endpoints:
            if modified_route in path:
                breaking_changes["modified"].append({
                    "path": path,
                    "change": description
                })
    
    # Identifier les nouveaux endpoints unifiés
    unified_patterns = ["/api/risk/advanced", "/api/alerts/resolve", "/governance/approve/"]
    for pattern in unified_patterns:
        for path in endpoints:
            if pattern in path:
                breaking_changes["new_unified"].append(path)
    
    # Changements de namespace
    namespace_changes = [
        ("/api/advanced-risk", "/api/risk/advanced"),
        ("/api/ml-predictions", "/api/ml")
    ]
    
    for old_ns, new_ns in namespace_changes:
        breaking_changes["namespace_changes"].append({
            "old": old_ns,
            "new": new_ns
        })
    
    return breaking_changes

def main():
    print("Verifying OpenAPI spec and identifying breaking changes...\n")
    
    try:
        # Charger la spec OpenAPI depuis le serveur en cours
        import requests
        response = requests.get("http://localhost:8000/openapi.json", timeout=10)
        
        if response.status_code != 200:
            print("ERROR Could not fetch OpenAPI spec from localhost:8000")
            print("   Make sure the server is running: uvicorn api.main:app --host localhost --port 8000")
            return 1
        
        spec = response.json()
        print("OK OpenAPI spec loaded successfully")
        
    except Exception as e:
        print(f"ERROR Error loading OpenAPI spec: {e}")
        return 1
    
    # Extraire les endpoints
    endpoints = extract_endpoints_from_spec(spec)
    print(f">> Found {len(endpoints)} endpoints total")
    
    # Identifier les breaking changes
    breaking_changes = identify_breaking_changes(endpoints)
    
    # Rapport détaillé
    print(f"\n{'='*60}")
    print(">> BREAKING CHANGES ANALYSIS")
    print(f"{'='*60}")
    
    # Routes supprimées
    if breaking_changes["removed"]:
        print(f"\n❌ REMOVED ENDPOINTS ({len(breaking_changes['removed'])}):")
        for route in breaking_changes["removed"]:
            print(f"  - {route}")
    else:
        print("\n✅ No removed endpoints found in current spec")
    
    # Routes modifiées
    if breaking_changes["modified"]:
        print(f"\n🔄 MODIFIED ENDPOINTS ({len(breaking_changes['modified'])}):")
        for item in breaking_changes["modified"]:
            print(f"  - {item['path']}")
            print(f"    Change: {item['change']}")
    else:
        print("\n✅ No modified endpoints detected")
    
    # Nouveaux endpoints unifiés
    if breaking_changes["new_unified"]:
        print(f"\n🆕 NEW UNIFIED ENDPOINTS ({len(breaking_changes['new_unified'])}):")
        for route in breaking_changes["new_unified"]:
            print(f"  + {route}")
    
    # Changements de namespace
    if breaking_changes["namespace_changes"]:
        print(f"\n🔀 NAMESPACE CHANGES:")
        for change in breaking_changes["namespace_changes"]:
            print(f"  {change['old']} → {change['new']}")
    
    # Validation des endpoints critiques
    print(f"\n{'='*60}")
    print("🔐 CRITICAL ENDPOINTS VALIDATION")
    print(f"{'='*60}")
    
    critical_endpoints = {
        "/api/alerts/acknowledge/{alert_id}": "Alert acknowledgment (centralized)",
        "/api/alerts/resolve/{alert_id}": "Alert resolution (centralized)", 
        "/api/governance/approve/{resource_id}": "Unified approval endpoint",
        "/api/risk/dashboard": "Main risk dashboard",
        "/api/risk/advanced/var/calculate": "Advanced VaR calculation",
        "/api/ml/status": "ML pipeline status",
        "/api/ml/debug/pipeline-info": "ML debug (admin-protected)"
    }
    
    for endpoint, description in critical_endpoints.items():
        found = False
        for path in endpoints:
            if endpoint.replace("{alert_id}", "").replace("{resource_id}", "") in path:
                found = True
                break
        
        status = "✅ FOUND" if found else "❌ MISSING"
        print(f"  {status}: {endpoint}")
        print(f"          {description}")
    
    # Recommandations
    print(f"\n{'='*60}")
    print("💡 MIGRATION RECOMMENDATIONS")
    print(f"{'='*60}")
    
    print("\n📋 For API Consumers:")
    print("  1. Update all /api/ml-predictions/* calls to /api/ml/*")
    print("  2. Remove all /api/test/* and /api/alerts/test/* calls")
    print("  3. Replace /api/advanced-risk/* with /api/risk/advanced/*")
    print("  4. Update /governance/approve calls to include resource_type in body")
    print("  5. Centralize alert resolution calls to /api/alerts/resolve/{id}")
    
    print("\n🔒 For Security:")
    print("  1. /api/realtime/publish and /broadcast are removed (security)")
    print("  2. /api/ml/debug/* now requires X-Admin-Key header")
    print("  3. Test endpoints removed from production")
    
    print("\n📝 For Documentation:")
    print("  1. Update API documentation with new endpoints")
    print("  2. Create migration guide for consumers") 
    print("  3. Update SDK clients and examples")
    print("  4. Bump API version to indicate breaking changes")
    
    # Résumé final
    total_breaking = (
        len(breaking_changes["removed"]) + 
        len(breaking_changes["modified"]) + 
        len(breaking_changes["namespace_changes"])
    )
    
    print(f"\n{'='*60}")
    if total_breaking == 0:
        print("🎉 NO BREAKING CHANGES DETECTED")
        return 0
    else:
        print(f"⚠️  {total_breaking} BREAKING CHANGES DETECTED")
        print("   Consumers will need to be updated before deploying")
        return 1

if __name__ == "__main__":
    sys.exit(main())