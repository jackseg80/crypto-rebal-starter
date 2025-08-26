#!/usr/bin/env python3
"""
Test manuel de la logique localStorage
"""

def analyze_rebalance_logic():
    """Analyser la logique de rebalance.html"""
    print("Analyse de la logique de rebalance.html")
    print("=" * 50)
    
    # Lire le fichier rebalance.html
    try:
        with open("static/rebalance.html", "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"ERREUR: Impossible de lire rebalance.html: {e}")
        return False
    
    # Vérifications de la logique de polling
    print("\n1. Vérification du polling localStorage:")
    
    checks = {
        "Fonction checkForNewTargets": "function checkForNewTargets()" in content,
        "Récupération currentTargets": "localStorage.getItem('last_targets')" in content,
        "Comparaison avec lastCheck": "currentTargets !== lastTargetsCheck" in content,
        "Parse JSON": "JSON.parse(currentTargets)" in content,
        "Vérification source": "targetsData.source === 'risk-dashboard-ccs'" in content,
        "Filtrage des targets": "typeof value === 'number'" in content,
        "Appel rebalanceAPI": "window.rebalanceAPI.setDynamicTargets" in content,
        "Interval de 2 secondes": "setInterval(checkForNewTargets, 2000)" in content
    }
    
    for check, result in checks.items():
        status = "✓" if result else "✗"
        print(f"   {status} {check}")
    
    # Vérifications de l'API rebalanceAPI
    print("\n2. Vérification de l'API rebalanceAPI:")
    
    api_checks = {
        "Déclaration window.rebalanceAPI": "window.rebalanceAPI = {" in content,
        "Fonction setDynamicTargets": "setDynamicTargets: function" in content,
        "Mise à jour dynamicTargets": "dynamicTargets = targets" in content,
        "Flag useDynamicTargets": "useDynamicTargets = true" in content,
        "Indicateur UI": "dynamicTargetsIndicator" in content,
        "Auto-run du plan": "runPlan()" in content,
        "getCurrentTargets": "getCurrentTargets: function" in content
    }
    
    for check, result in api_checks.items():
        status = "✓" if result else "✗"
        print(f"   {status} {check}")
    
    # Vérifications de buildPayload
    print("\n3. Vérification de buildPayload:")
    
    payload_checks = {
        "Fonction buildPayload": "function buildPayload()" in content,
        "Vérification useDynamicTargets": "if (useDynamicTargets && dynamicTargets)" in content,
        "Utilisation dynamic_targets_pct": "payload.dynamic_targets_pct = dynamicTargets" in content,
        "Fallback group_targets_pct": "payload.group_targets_pct = {" in content
    }
    
    for check, result in payload_checks.items():
        status = "✓" if result else "✗"
        print(f"   {status} {check}")
    
    # Problèmes potentiels identifiés
    print("\n4. Problèmes potentiels:")
    
    problems = []
    
    # Vérifier l'extraction du score CCS
    if "targetsData.strategy.match(/\\d+/)" in content:
        print("   ✓ Extraction du score CCS avec regex")
    else:
        problems.append("Extraction du score CCS manquante ou incorrecte")
    
    # Vérifier la gestion des erreurs
    if "catch (error)" in content:
        print("   ✓ Gestion d'erreur présente")
    else:
        problems.append("Pas de gestion d'erreur pour le parsing JSON")
    
    # Vérifier l'initialisation
    if "lastTargetsCheck = localStorage.getItem('last_targets')" in content:
        print("   ✓ Initialisation de lastTargetsCheck")
    else:
        problems.append("Initialisation de lastTargetsCheck manquante")
    
    # Vérifier l'appel immédiat
    if "checkForNewTargets();" in content:
        print("   ✓ Vérification immédiate au chargement")
    else:
        problems.append("Pas de vérification immédiate au chargement")
    
    if problems:
        print("\n   PROBLÈMES DÉTECTÉS:")
        for problem in problems:
            print(f"   ✗ {problem}")
    
    # Test manuel suggéré
    print("\n" + "=" * 50)
    print("TEST MANUEL SUGGÉRÉ")
    print("=" * 50)
    
    test_script = '''
// 1. Ouvrir http://localhost:8000/static/rebalance.html
// 2. Ouvrir DevTools (F12) et aller dans Console
// 3. Coller et exécuter ce script:

console.log("🧪 Test manuel de la communication localStorage");

// Vérifier l'état initial
console.log("📊 État initial:");
console.log("  useDynamicTargets:", typeof useDynamicTargets !== 'undefined' ? useDynamicTargets : 'undefined');
console.log("  dynamicTargets:", typeof dynamicTargets !== 'undefined' ? dynamicTargets : 'undefined');
console.log("  rebalanceAPI:", typeof window.rebalanceAPI !== 'undefined' ? 'défini' : 'undefined');

// Simuler des données du risk dashboard
const testData = {
    targets: {
        "BTC": 40.0,
        "ETH": 30.0,
        "Stablecoins": 15.0,
        "L1/L0 majors": 10.0,
        "Others": 5.0
    },
    timestamp: new Date().toISOString(),
    strategy: "Test Manual CCS 65",
    source: "risk-dashboard-ccs"
};

console.log("💾 Sauvegarde des données de test...");
localStorage.setItem('last_targets', JSON.stringify(testData));

console.log("⏳ Attendre 3 secondes pour voir si le polling détecte...");
setTimeout(() => {
    console.log("📊 État après 3 secondes:");
    console.log("  useDynamicTargets:", useDynamicTargets);
    console.log("  dynamicTargets:", dynamicTargets);
    
    // Vérifier l'indicateur UI
    const indicator = document.getElementById('dynamicTargetsIndicator');
    console.log("  Indicateur visible:", indicator ? indicator.style.display !== 'none' : 'element not found');
}, 3000);
'''
    
    print(test_script)
    
    return True

if __name__ == "__main__":
    analyze_rebalance_logic()