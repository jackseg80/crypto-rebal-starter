#!/usr/bin/env python3
"""
Rapport de synthèse simple des tests E2E Phase 3
"""
import json
import os
from datetime import datetime

def load_test_file(filename):
    """Charger un fichier JSON de test"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        return {"error": str(e)}

def main():
    """Générer le rapport simple"""
    print("=== Phase 3 E2E Test Report ===")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Charger les résultats
    integration = load_test_file("phase3_test_results.json")
    resilience = load_test_file("phase3_resilience_results.json") 
    performance = load_test_file("phase3_performance_benchmark.json")
    compatibility = load_test_file("phase3_compatibility_results.json")
    
    # Résumé Integration
    if integration and "var" in integration:
        print("[PASS] Integration Tests: PASSED")
        print(f"   VaR Parametric: ${integration['var']['param_var']:.2f}")
        print(f"   VaR Historical: ${integration['var']['hist_var']:.2f}")
        print(f"   Duration: {integration['var']['duration_ms']}ms")
    else:
        print("[FAIL] Integration Tests: FAILED")
    
    # Résumé Resilience  
    if resilience and "summary" in resilience:
        score = resilience["summary"]["overall_resilience_score"]
        print(f"[PASS] Resilience Tests: {score}/100")
        print(f"   WebSocket Recovery: {resilience['summary']['websocket_resilience']}")
        print(f"   Error Recovery: {resilience['summary']['error_recovery']}")
    else:
        print("[FAIL] Resilience Tests: FAILED")
    
    # Résumé Performance
    if performance and "summary" in performance:
        score = performance["summary"]["performance_score"]
        avg_ms = performance["summary"]["var_api_avg_ms"]
        print(f"[PASS] Performance Tests: {score}/100")
        print(f"   VaR API Average: {avg_ms}ms")
        print(f"   Concurrent Success: {performance['summary']['concurrent_success_rate']}%")
    else:
        print("[FAIL] Performance Tests: FAILED")
    
    # Résumé Compatibility
    if compatibility and "summary" in compatibility:
        score = compatibility["summary"]["overall_compatibility_score"]
        rating = compatibility["summary"]["compatibility_rating"]
        print(f"[PASS] Compatibility Tests: {score}/100 ({rating})")
        print(f"   JavaScript Score: {compatibility['summary']['javascript_score']}/100")
        print(f"   Responsive Score: {compatibility['summary']['responsive_score']}/100")
    else:
        print("[FAIL] Compatibility Tests: FAILED")
    
    print()
    print("=== Overall Assessment ===")
    
    # Calculer score global
    scores = []
    if integration: scores.append(100)  # Integration binaire
    if resilience and "summary" in resilience: 
        scores.append(resilience["summary"]["overall_resilience_score"])
    if performance and "summary" in performance:
        scores.append(performance["summary"]["performance_score"]) 
    if compatibility and "summary" in compatibility:
        scores.append(compatibility["summary"]["overall_compatibility_score"])
    
    if scores:
        overall = sum(scores) / len(scores)
        print(f"Overall Score: {overall:.1f}/100")
        
        if overall >= 90:
            print("Status: EXCELLENT - Ready for production")
        elif overall >= 75:
            print("Status: GOOD - Minor optimizations recommended")
        elif overall >= 60:
            print("Status: ACCEPTABLE - Some improvements needed")
        else:
            print("Status: NEEDS_WORK - Significant issues to address")
    else:
        print("Status: INCOMPLETE - No test results found")
    
    print()
    print("Files Test result files:")
    for filename in ["phase3_test_results.json", "phase3_resilience_results.json", 
                    "phase3_performance_benchmark.json", "phase3_compatibility_results.json"]:
        status = "[OK]" if os.path.exists(filename) else "[MISSING]"
        print(f"   {status} {filename}")

if __name__ == "__main__":
    main()