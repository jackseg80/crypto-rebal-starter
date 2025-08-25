#!/usr/bin/env python3
"""
Test de l'intégration de la stratégie dynamique CCS
"""

import requests
import json

def test_integration():
    """Test l'intégration complète stratégie dynamique"""
    print("Test de l'intégration stratégie dynamique CCS")
    print("=" * 50)
    
    BASE_URL = "http://localhost:8000"
    
    # Test 1: Vérifier rebalance.html
    print("\n1. Test rebalance.html - Fonction syncCCSTargets...")
    try:
        resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=10)
        if resp.status_code == 200:
            content = resp.text
            
            has_sync_function = "function syncCCSTargets()" in content
            has_refresh_function = "window.refreshDynamicStrategy" in content
            has_sync_button = '"🎯 Sync CCS"' in content
            has_dynamic_strategy = "Strategic (Dynamic)" in content
            no_old_polling = "setInterval(checkForNewTargets" not in content
            
            print(f"   ✓ Fonction syncCCSTargets: {'OUI' if has_sync_function else 'NON'}")
            print(f"   ✓ Fonction refreshDynamicStrategy: {'OUI' if has_refresh_function else 'NON'}")
            print(f"   ✓ Bouton Sync CCS: {'OUI' if has_sync_button else 'NON'}")
            print(f"   ✓ Stratégie dynamique: {'OUI' if has_dynamic_strategy else 'NON'}")
            print(f"   ✓ Ancien polling supprimé: {'OUI' if no_old_polling else 'NON'}")
            
            if all([has_sync_function, has_refresh_function, has_sync_button, has_dynamic_strategy, no_old_polling]):
                print("   ✅ rebalance.html correctement modifié")
            else:
                print("   ❌ Certaines modifications manquent dans rebalance.html")
                
        else:
            print(f"   ❌ Impossible d'accéder à rebalance.html (HTTP {resp.status_code})")
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # Test 2: Vérifier risk-dashboard.html
    print("\n2. Test risk-dashboard.html - Apply Targets simplifié...")
    try:
        resp = requests.get(f"{BASE_URL}/static/risk-dashboard.html", timeout=10)
        if resp.status_code == 200:
            content = resp.text
            
            has_localstorage_save = "localStorage.setItem('last_targets'" in content
            has_simplified_feedback = "Saved to CCS!" in content
            has_instruction = "Allez sur rebalance.html et cliquez" in content
            no_auto_apply = "await applyTargets(blendedProposal)" not in content
            
            print(f"   ✓ Sauvegarde localStorage: {'OUI' if has_localstorage_save else 'NON'}")
            print(f"   ✓ Feedback simplifié: {'OUI' if has_simplified_feedback else 'NON'}")
            print(f"   ✓ Instructions utilisateur: {'OUI' if has_instruction else 'NON'}")
            print(f"   ✓ Auto-apply supprimé: {'OUI' if no_auto_apply else 'NON'}")
            
            if all([has_localstorage_save, has_simplified_feedback, has_instruction, no_auto_apply]):
                print("   ✅ risk-dashboard.html correctement modifié")
            else:
                print("   ❌ Certaines modifications manquent dans risk-dashboard.html")
                
        else:
            print(f"   ❌ Impossible d'accéder à risk-dashboard.html (HTTP {resp.status_code})")
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # Test 3: Simuler le workflow complet
    print("\n3. Test du workflow complet...")
    print("\n" + "=" * 50)
    print("INSTRUCTIONS DE TEST MANUEL")
    print("=" * 50)
    print("""
🧪 POUR TESTER LA NOUVELLE INTÉGRATION:

1. RISK DASHBOARD:
   - Ouvrir: http://localhost:8000/static/risk-dashboard.html
   - Aller dans l'onglet "Strategic Targets"
   - Cliquer sur "✅ Apply Targets"
   - Vérifier le message: "Targets CCS sauvegardés!"

2. REBALANCE:
   - Ouvrir: http://localhost:8000/static/rebalance.html
   - Cliquer sur "🎯 Sync CCS" (bouton orange)
   - Vérifier qu'une nouvelle stratégie "🎯 Strategic (Dynamic)" apparaît
   - Cette stratégie devrait avoir un fond orange et mention "Données récentes"
   
3. UTILISATION:
   - Sélectionner la stratégie "🎯 Strategic (Dynamic)"
   - Cliquer "✅ Appliquer la Stratégie"
   - Cliquer "Générer le plan" (optionnel)
   - Le plan devrait utiliser les allocations du Risk Dashboard

RÉSULTATS ATTENDUS:
✓ Plus de polling automatique toutes les 2 secondes
✓ Plus d'auto-génération de plan non désirée
✓ Contrôle total de l'utilisateur
✓ Interface unifiée dans rebalance.html
✓ Synchronisation manuelle via le bouton "🎯 Sync CCS"
✓ Stratégie CCS visible parmi les stratégies prédéfinies
""")

if __name__ == "__main__":
    test_integration()