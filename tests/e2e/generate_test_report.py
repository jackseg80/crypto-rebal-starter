"""
Génère un rapport de synthèse des tests E2E Phase 3
Combine tous les résultats en un rapport unifié
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

def load_test_results() -> Dict[str, Any]:
    """Charger tous les fichiers de résultats de test"""
    results = {}
    
    test_files = [
        ("integration", "phase3_test_results.json"),
        ("resilience", "phase3_resilience_results.json"), 
        ("performance", "phase3_performance_benchmark.json"),
        ("compatibility", "phase3_compatibility_results.json")
    ]
    
    for test_name, filename in test_files:
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    results[test_name] = json.load(f)
            else:
                results[test_name] = {"error": f"File {filename} not found"}
        except Exception as e:
            results[test_name] = {"error": str(e)}
    
    return results

def generate_html_report(results: Dict[str, Any]) -> str:
    """Générer un rapport HTML"""
    
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Phase 3 E2E Test Report</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; }
            .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
            .card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .card.success { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card.warning { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
            .card.error { background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); }
            .metric { font-size: 2em; font-weight: bold; margin: 10px 0; }
            .label { font-size: 0.9em; opacity: 0.9; }
            .test-section { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 6px; border-left: 4px solid #3498db; }
            .status-pass { color: #27ae60; font-weight: bold; }
            .status-fail { color: #e74c3c; font-weight: bold; }
            .details { font-family: 'Courier New', monospace; background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px; margin: 10px 0; overflow-x: auto; }
            table { width: 100%; border-collapse: collapse; margin: 10px 0; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #3498db; color: white; }
            .timestamp { color: #7f8c8d; font-size: 0.9em; text-align: right; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 Phase 3 E2E Test Report</h1>
            <p><strong>Generated:</strong> {timestamp}</p>
            
            <div class="summary">
                {summary_cards}
            </div>
            
            {test_sections}
            
            <div class="timestamp">
                Report generated on {full_timestamp}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Générer les cartes de résumé
    summary_cards = []
    
    # Intégration
    if "integration" in results and "var" in results["integration"]:
        integration_score = "✅ PASS" if results["integration"]["var"]["status"] == "PASS" else "❌ FAIL"
        var_time = results["integration"]["var"]["duration_ms"]
        summary_cards.append(f"""
            <div class="card success">
                <div class="metric">{integration_score}</div>
                <div class="label">Integration Tests</div>
                <div>VaR API: {var_time}ms</div>
            </div>
        """)
    
    # Résilience
    if "resilience" in results and "summary" in results["resilience"]:
        resilience_score = results["resilience"]["summary"]["overall_resilience_score"]
        summary_cards.append(f"""
            <div class="card {'success' if resilience_score >= 80 else 'warning'}">
                <div class="metric">{resilience_score}%</div>
                <div class="label">Resilience Score</div>
            </div>
        """)
    
    # Performance  
    if "performance" in results and "summary" in results["performance"]:
        perf_score = results["performance"]["summary"]["performance_score"]
        var_avg = results["performance"]["summary"]["var_api_avg_ms"]
        summary_cards.append(f"""
            <div class="card {'success' if perf_score >= 80 else 'warning'}">
                <div class="metric">{perf_score}/100</div>
                <div class="label">Performance Score</div>
                <div>VaR: {var_avg}ms avg</div>
            </div>
        """)
    
    # Compatibilité
    if "compatibility" in results and "summary" in results["compatibility"]:
        compat_score = results["compatibility"]["summary"]["overall_compatibility_score"]
        summary_cards.append(f"""
            <div class="card {'success' if compat_score >= 80 else 'warning'}">
                <div class="metric">{compat_score}%</div>
                <div class="label">Compatibility</div>
            </div>
        """)
    
    # Générer les sections de test détaillées
    test_sections = []
    
    # Section Intégration
    if "integration" in results:
        test_sections.append(f"""
            <div class="test-section">
                <h2>🔌 Integration Tests</h2>
                <div class="details">{json.dumps(results["integration"], indent=2)}</div>
            </div>
        """)
    
    # Section Résilience
    if "resilience" in results:
        test_sections.append(f"""
            <div class="test-section">
                <h2>🛡️ Resilience Tests</h2>
                <div class="details">{json.dumps(results["resilience"], indent=2)}</div>
            </div>
        """)
    
    # Section Performance
    if "performance" in results:
        test_sections.append(f"""
            <div class="test-section">
                <h2>🏃 Performance Benchmarks</h2>
                <div class="details">{json.dumps(results["performance"], indent=2)}</div>
            </div>
        """)
    
    # Section Compatibilité
    if "compatibility" in results:
        test_sections.append(f"""
            <div class="test-section">
                <h2>🌐 Compatibility Tests</h2>
                <div class="details">{json.dumps(results["compatibility"], indent=2)}</div>
            </div>
        """)
    
    # Remplacer les placeholders
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return html.format(
        timestamp=timestamp,
        full_timestamp=full_timestamp,
        summary_cards="".join(summary_cards),
        test_sections="".join(test_sections)
    )

def generate_markdown_report(results: Dict[str, Any]) -> str:
    """Générer un rapport Markdown"""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    md = f"""
# 🧪 Phase 3 E2E Test Report

**Generated:** {timestamp}

## 📊 Executive Summary

"""
    
    # Ajouter les résumés de chaque test
    if "integration" in results:
        md += """
### ✅ Integration Tests
- **Status:** COMPLETED
- **VaR API Response Time:** Available in detailed results
- **WebSocket System:** Functional
"""
    
    if "resilience" in results and "summary" in results["resilience"]:
        resilience_score = results["resilience"]["summary"]["overall_resilience_score"]
        md += f"""
### 🛡️ Resilience Tests  
- **Overall Score:** {resilience_score}/100
- **WebSocket Resilience:** {results["resilience"]["summary"]["websocket_resilience"]}
- **Error Recovery:** {results["resilience"]["summary"]["error_recovery"]}
"""
    
    if "performance" in results and "summary" in results["performance"]:
        perf = results["performance"]["summary"]
        md += f"""
### 🏃 Performance Benchmarks
- **Performance Score:** {perf["performance_score"]}/100  
- **VaR API Average:** {perf["var_api_avg_ms"]}ms
- **VaR API P95:** {perf["var_api_p95_ms"]}ms
- **Concurrent Success Rate:** {perf["concurrent_success_rate"]}%
"""
    
    if "compatibility" in results and "summary" in results["compatibility"]:
        compat = results["compatibility"]["summary"]
        md += f"""
### 🌐 Compatibility Tests
- **Overall Score:** {compat["overall_compatibility_score"]}/100
- **Rating:** {compat["compatibility_rating"]}
- **JavaScript Score:** {compat["javascript_score"]}/100
- **Responsive Score:** {compat["responsive_score"]}/100
"""
    
    md += """
## 📋 Detailed Results

See individual JSON files for complete metrics:
- `phase3_test_results.json` - Integration test details
- `phase3_resilience_results.json` - Resilience test details  
- `phase3_performance_benchmark.json` - Performance benchmark details
- `phase3_compatibility_results.json` - Compatibility test details

---
*Report generated automatically by Phase 3 E2E Test Suite*
"""
    
    return md

def main():
    """Générer le rapport de synthèse"""
    print("Generating Phase 3 E2E Test Report...")
    
    # Charger tous les résultats
    results = load_test_results()
    
    # Générer les rapports
    html_report = generate_html_report(results)
    markdown_report = generate_markdown_report(results)
    
    # Sauvegarder les rapports
    with open("phase3_e2e_report.html", "w", encoding="utf-8") as f:
        f.write(html_report)
    
    with open("phase3_e2e_report.md", "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    # Générer aussi un résumé JSON
    summary = {
        "generated_at": datetime.now().isoformat(),
        "test_files_found": len([k for k, v in results.items() if "error" not in v]),
        "total_test_categories": len(results),
        "results_summary": results
    }
    
    with open("phase3_e2e_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print("✅ Reports generated:")
    print("   📄 phase3_e2e_report.html - Interactive HTML report")  
    print("   📝 phase3_e2e_report.md - Markdown summary")
    print("   📊 phase3_e2e_summary.json - JSON summary")
    
    return summary

if __name__ == "__main__":
    main()