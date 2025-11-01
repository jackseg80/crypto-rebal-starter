"""
Test de compatibilité simplifié sans Selenium
Valide les aspects critiques pour la compatibilité navigateur
"""
import json
import requests
import re
from typing import Dict, Any

def test_web_compatibility():
    """Test de compatibilité web simplifié"""
    base_url = "http://localhost:8080"
    session = requests.Session()
    
    print("Phase 3 Web Compatibility Tests")
    print("=" * 35)
    
    results = {}
    
    # Test 1: HTML/CSS Validity
    print("1. Testing HTML/CSS Structure...")
    
    # Récupérer le contenu HTML du Risk Dashboard
    response = session.get(f"{base_url}/static/risk-dashboard.html")
    assert response.status_code == 200
    html_content = response.text
    
    # Vérifications de compatibilité HTML
    html_checks = {
        "has_doctype": html_content.strip().startswith("<!DOCTYPE html>"),
        "has_meta_viewport": 'name="viewport"' in html_content,
        "uses_semantic_html": any(tag in html_content for tag in ["<header>", "<nav>", "<main>", "<section>"]),
        "has_css_classes": "class=" in html_content,
        "uses_modern_css": any(prop in html_content for prop in ["flexbox", "grid", "var(--", ":root"]),
        "has_responsive_design": "@media" in html_content
    }
    
    html_score = (sum(html_checks.values()) / len(html_checks)) * 100
    
    results["html_compatibility"] = {
        "score": round(html_score, 1),
        "checks": html_checks
    }
    
    print(f"   [OK] HTML/CSS compatibility: {html_score:.1f}%")
    
    # Test 2: JavaScript Compatibility
    print("2. Testing JavaScript Features...")
    
    # Vérifier les patterns JavaScript utilisés
    js_patterns = {
        "uses_es6_features": any(pattern in html_content for pattern in ["const ", "let ", "=>", "async ", "await "]),
        "uses_fetch_api": "fetch(" in html_content,
        "uses_modern_dom": any(method in html_content for method in ["querySelector", "addEventListener"]),
        "has_error_handling": any(pattern in html_content for pattern in ["try {", "catch (", ".catch("]),
        "uses_modules": 'type="module"' in html_content,
        "uses_localstorage": "localStorage" in html_content
    }
    
    js_score = (sum(js_patterns.values()) / len(js_patterns)) * 100
    
    results["javascript_compatibility"] = {
        "score": round(js_score, 1),
        "patterns": js_patterns
    }
    
    print(f"   [OK] JavaScript compatibility: {js_score:.1f}%")
    
    # Test 3: API Response Headers
    print("3. Testing API Headers...")
    
    # Vérifier les headers CORS et de sécurité
    api_response = session.get(f"{base_url}/api/phase3/status")
    headers = api_response.headers
    
    security_headers = {
        "has_cors_headers": "access-control-allow-origin" in headers,
        "has_content_type": "content-type" in headers,
        "json_response": "application/json" in headers.get("content-type", ""),
        "has_cache_control": "cache-control" in headers
    }
    
    headers_score = (sum(security_headers.values()) / len(security_headers)) * 100
    
    results["api_headers"] = {
        "score": round(headers_score, 1),
        "headers": security_headers
    }
    
    print(f"   [OK] API headers compatibility: {headers_score:.1f}%")
    
    # Test 4: WebSocket Compatibility
    print("4. Testing WebSocket Support...")
    
    # Vérifier que le système WebSocket est disponible
    ws_status = session.get(f"{base_url}/api/realtime/status")
    ws_connections = session.get(f"{base_url}/api/realtime/connections")
    
    websocket_support = {
        "realtime_api_available": ws_status.status_code == 200,
        "connections_api_available": ws_connections.status_code == 200,
        "websocket_url_correct": "ws://" in html_content or "wss://" in html_content,
        "fallback_implemented": "setInterval" in html_content  # Polling fallback
    }
    
    ws_score = (sum(websocket_support.values()) / len(websocket_support)) * 100
    
    results["websocket_compatibility"] = {
        "score": round(ws_score, 1),
        "support": websocket_support
    }
    
    print(f"   [OK] WebSocket compatibility: {ws_score:.1f}%")
    
    # Test 5: Mobile/Responsive Compatibility
    print("5. Testing Responsive Design...")
    
    # Analyser les CSS pour la responsivité
    responsive_features = {
        "has_media_queries": "@media" in html_content,
        "uses_flexible_units": any(unit in html_content for unit in ["rem", "em", "vh", "vw", "%"]),
        "has_mobile_meta": 'name="viewport"' in html_content,
        "uses_flexbox": any(flex in html_content for flex in ["display: flex", "flex:", "align-items", "justify-content"]),
        "responsive_navigation": "mobile" in html_content.lower() or "tablet" in html_content.lower()
    }
    
    responsive_score = (sum(responsive_features.values()) / len(responsive_features)) * 100
    
    results["responsive_compatibility"] = {
        "score": round(responsive_score, 1),
        "features": responsive_features
    }
    
    print(f"   [OK] Responsive design: {responsive_score:.1f}%")
    
    # Test 6: Performance Indicators
    print("6. Testing Performance Features...")
    
    # Vérifier les optimisations de performance
    performance_features = {
        "lazy_loading": "lazy" in html_content.lower(),
        "async_scripts": "async" in html_content,
        "defer_scripts": "defer" in html_content,
        "caching_strategy": any(cache in html_content for cache in ["cache", "etag", "last-modified"]),
        "minified_resources": ".min." in html_content,
        "cdn_usage": any(cdn in html_content for cdn in ["cdn", "cloudflare", "jsdelivr"])
    }
    
    performance_score = (sum(performance_features.values()) / len(performance_features)) * 100
    
    results["performance_features"] = {
        "score": round(performance_score, 1),
        "optimizations": performance_features
    }
    
    print(f"   [OK] Performance optimizations: {performance_score:.1f}%")
    
    # Calculer le score global
    all_scores = [
        results["html_compatibility"]["score"],
        results["javascript_compatibility"]["score"],
        results["api_headers"]["score"],
        results["websocket_compatibility"]["score"],
        results["responsive_compatibility"]["score"],
        results["performance_features"]["score"]
    ]
    
    overall_score = sum(all_scores) / len(all_scores)
    
    results["summary"] = {
        "overall_compatibility_score": round(overall_score, 1),
        "html_css_score": results["html_compatibility"]["score"],
        "javascript_score": results["javascript_compatibility"]["score"],
        "api_score": results["api_headers"]["score"],
        "websocket_score": results["websocket_compatibility"]["score"],
        "responsive_score": results["responsive_compatibility"]["score"],
        "performance_score": results["performance_features"]["score"],
        "compatibility_rating": (
            "EXCELLENT" if overall_score >= 90 else
            "GOOD" if overall_score >= 75 else
            "ACCEPTABLE" if overall_score >= 60 else
            "NEEDS_IMPROVEMENT"
        )
    }
    
    print("=" * 35)
    print(f"Overall Compatibility Score: {overall_score:.1f}/100")
    print(f"Rating: {results['summary']['compatibility_rating']}")
    
    if overall_score >= 90:
        print("Excellent cross-browser compatibility!")
    elif overall_score >= 75:
        print("Good compatibility with minor improvements needed")
    else:
        print("Compatibility issues detected - review recommendations")
    
    # Sauvegarder les résultats
    with open("phase3_compatibility_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Compatibility results saved to: phase3_compatibility_results.json")
    
    return results

if __name__ == "__main__":
    test_web_compatibility()
