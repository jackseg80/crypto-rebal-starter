"""
Service de portfolio analytics - calculs de performance, métriques, etc.
"""

from __future__ import annotations
import os
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class PortfolioAnalytics:
    """Service d'analyse de portfolio avec calculs de performance"""
    
    def __init__(self):
        self.historical_data_file = os.path.join("data", "portfolio_history.json")
        
    def calculate_portfolio_metrics(self, balances_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcule les métriques principales du portfolio
        
        Args:
            balances_data: Données de balance depuis /balances/current
            
        Returns:
            Dict avec métriques calculées
        """
        items = balances_data.get("items", [])
        
        # Filtrer les items avec valeur et enrichir avec les groupes
        valid_items = []
        for item in items:
            usd_val = item.get("usd_value", 0) or item.get("value_usd", 0)
            if usd_val > 0:
                # Normaliser le format
                item_copy = item.copy()
                item_copy["usd_value"] = usd_val
                
                # Enrichir avec le groupe depuis la taxonomie
                symbol = item.get("symbol", "")
                alias = item.get("alias", symbol)
                group = self._get_group_for_symbol(alias)
                item_copy["group"] = group
                
                valid_items.append(item_copy)
        
        if not valid_items:
            return self._empty_metrics()
        
        # Calculs de base
        total_value = sum(item.get("usd_value", 0) for item in valid_items)
        asset_count = len(valid_items)
        
        # Top holding
        top_holding = max(valid_items, key=lambda x: x.get("usd_value", 0))
        top_holding_percentage = top_holding.get("usd_value", 0) / total_value if total_value > 0 else 0
        
        # Diversité par groupe
        groups = {}
        for item in valid_items:
            group = item.get("group", "Others")
            groups[group] = groups.get(group, 0) + item.get("usd_value", 0)
        
        group_count = len(groups)
        largest_group_percentage = max(groups.values()) / total_value if total_value > 0 else 0
        
        # Score de diversification (0-10)
        diversity_score = self._calculate_diversity_score(
            asset_count, group_count, top_holding_percentage, largest_group_percentage
        )
        
        # Recommandations de rebalancing
        rebalance_recommendations = self._generate_rebalance_recommendations(
            valid_items, total_value, groups
        )
        
        return {
            "total_value_usd": total_value,
            "asset_count": asset_count,
            "group_count": group_count,
            "top_holding": {
                "symbol": top_holding.get("symbol"),
                "value_usd": top_holding.get("usd_value", 0),
                "percentage": top_holding_percentage
            },
            "diversity_score": diversity_score,
            "concentration_risk": "High" if top_holding_percentage > 0.5 else "Medium" if top_holding_percentage > 0.3 else "Low",
            "group_distribution": groups,
            "largest_group_percentage": largest_group_percentage,
            "rebalance_recommendations": rebalance_recommendations,
            "last_updated": datetime.now().isoformat()
        }
    
    def calculate_performance_metrics(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcule les métriques de performance vs historique
        
        Args:
            current_data: Données actuelles du portfolio
            
        Returns:
            Dict avec métriques de performance
        """
        historical_data = self._load_historical_data()
        
        if not historical_data:
            return {
                "performance_available": False,
                "message": "Pas de données historiques disponibles",
                "days_tracked": 0
            }
        
        # Comparer avec la dernière entrée historique
        latest_historical = historical_data[-1] if historical_data else None
        
        if not latest_historical:
            return {
                "performance_available": False,
                "message": "Pas de données historiques valides",
                "days_tracked": 0
            }
        
        current_value = current_data.get("total_value_usd", 0)
        historical_value = latest_historical.get("total_value_usd", 0)
        
        if historical_value == 0:
            return {
                "performance_available": False,
                "message": "Valeur historique invalide",
                "days_tracked": len(historical_data)
            }
        
        # Calculs de performance
        absolute_change = current_value - historical_value
        percentage_change = (absolute_change / historical_value) * 100
        
        # Période de suivi
        historical_date = datetime.fromisoformat(latest_historical.get("date", datetime.now().isoformat()))
        days_tracked = (datetime.now() - historical_date).days
        
        # Performance annualisée (approximative)
        if days_tracked > 0:
            daily_return = (current_value / historical_value) ** (1/days_tracked) - 1
            annualized_return = ((1 + daily_return) ** 365 - 1) * 100
        else:
            annualized_return = 0
        
        return {
            "performance_available": True,
            "current_value_usd": current_value,
            "historical_value_usd": historical_value,
            "absolute_change_usd": absolute_change,
            "percentage_change": percentage_change,
            "days_tracked": days_tracked,
            "annualized_return_estimate": annualized_return,
            "performance_status": "gain" if absolute_change > 0 else "loss" if absolute_change < 0 else "neutral",
            "comparison_date": latest_historical.get("date"),
            "historical_entries_count": len(historical_data)
        }
    
    def save_portfolio_snapshot(self, balances_data: Dict[str, Any]) -> bool:
        """
        Sauvegarde un snapshot du portfolio pour suivi historique
        
        Args:
            balances_data: Données de balance actuelles
            
        Returns:
            True si sauvé avec succès
        """
        try:
            metrics = self.calculate_portfolio_metrics(balances_data)
            
            snapshot = {
                "date": datetime.now().isoformat(),
                "total_value_usd": metrics["total_value_usd"],
                "asset_count": metrics["asset_count"],
                "group_count": metrics["group_count"],
                "diversity_score": metrics["diversity_score"],
                "top_holding_symbol": metrics["top_holding"]["symbol"],
                "top_holding_percentage": metrics["top_holding"]["percentage"],
                "group_distribution": metrics["group_distribution"]
            }
            
            # Charger données existantes
            historical_data = self._load_historical_data()
            
            # Ajouter nouveau snapshot
            historical_data.append(snapshot)
            
            # Garder seulement les 365 derniers jours
            if len(historical_data) > 365:
                historical_data = historical_data[-365:]
            
            # Sauvegarder
            os.makedirs(os.path.dirname(self.historical_data_file), exist_ok=True)
            with open(self.historical_data_file, 'w', encoding='utf-8') as f:
                json.dump(historical_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Portfolio snapshot sauvé ({metrics['total_value_usd']:.2f} USD)")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde snapshot: {e}")
            return False
    
    def get_portfolio_trend(self, days: int = 30) -> Dict[str, Any]:
        """
        Retourne les données de tendance du portfolio
        
        Args:
            days: Nombre de jours d'historique à retourner
            
        Returns:
            Données de tendance pour graphiques
        """
        historical_data = self._load_historical_data()
        
        if not historical_data:
            return {"trend_data": [], "days_available": 0}
        
        # Filtrer les derniers jours
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_data = [
            entry for entry in historical_data
            if datetime.fromisoformat(entry.get("date", "")) >= cutoff_date
        ]
        
        # Formater pour le frontend
        trend_data = []
        for entry in filtered_data:
            trend_data.append({
                "date": entry.get("date"),
                "total_value": entry.get("total_value_usd", 0),
                "asset_count": entry.get("asset_count", 0),
                "diversity_score": entry.get("diversity_score", 0)
            })
        
        return {
            "trend_data": trend_data,
            "days_available": len(trend_data),
            "oldest_date": trend_data[0]["date"] if trend_data else None,
            "newest_date": trend_data[-1]["date"] if trend_data else None
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Retourne des métriques vides"""
        return {
            "total_value_usd": 0,
            "asset_count": 0,
            "group_count": 0,
            "top_holding": {"symbol": "N/A", "value_usd": 0, "percentage": 0},
            "diversity_score": 0,
            "concentration_risk": "Unknown",
            "group_distribution": {},
            "largest_group_percentage": 0,
            "rebalance_recommendations": [],
            "last_updated": datetime.now().isoformat()
        }
    
    def _calculate_diversity_score(self, asset_count: int, group_count: int, 
                                 top_holding_pct: float, largest_group_pct: float) -> int:
        """
        Calcule un score de diversification de 0 à 10
        
        Args:
            asset_count: Nombre d'assets
            group_count: Nombre de groupes
            top_holding_pct: Pourcentage du plus gros holding
            largest_group_pct: Pourcentage du plus gros groupe
            
        Returns:
            Score de 0 à 10
        """
        score = 0
        
        # Points pour nombre d'assets (max 3 points)
        if asset_count >= 10:
            score += 3
        elif asset_count >= 5:
            score += 2
        elif asset_count >= 3:
            score += 1
        
        # Points pour nombre de groupes (max 2 points)
        if group_count >= 4:
            score += 2
        elif group_count >= 3:
            score += 1
        
        # Pénalités pour concentration (max -3 points)
        if top_holding_pct > 0.6:
            score -= 3
        elif top_holding_pct > 0.4:
            score -= 2
        elif top_holding_pct > 0.25:
            score -= 1
        
        # Pénalités pour concentration de groupe (max -2 points)
        if largest_group_pct > 0.8:
            score -= 2
        elif largest_group_pct > 0.6:
            score -= 1
        
        # Bonus pour équilibre (max +3 points)
        if top_holding_pct < 0.2 and largest_group_pct < 0.4:
            score += 3
        elif top_holding_pct < 0.3 and largest_group_pct < 0.5:
            score += 2
        elif top_holding_pct < 0.4 and largest_group_pct < 0.6:
            score += 1
        
        return max(0, min(10, score))
    
    def _generate_rebalance_recommendations(self, items: List[Dict], 
                                          total_value: float, groups: Dict[str, float]) -> List[str]:
        """Génère des recommandations de rebalancing"""
        recommendations = []
        
        if not items or total_value == 0:
            return recommendations
        
        # Analyser la concentration
        top_holding = max(items, key=lambda x: x.get("usd_value", 0))
        top_pct = top_holding.get("usd_value", 0) / total_value
        
        if top_pct > 0.5:
            recommendations.append(f"⚠️ Forte concentration sur {top_holding['symbol']} ({top_pct:.1%})")
        
        # Analyser les groupes
        largest_group = max(groups.items(), key=lambda x: x[1]) if groups else ("", 0)
        largest_group_pct = largest_group[1] / total_value if total_value > 0 else 0
        
        if largest_group_pct > 0.7:
            recommendations.append(f"📊 Diversifier hors du groupe {largest_group[0]} ({largest_group_pct:.1%})")
        
        # Recommandations générales
        if len(items) < 3:
            recommendations.append("🎯 Envisager plus d'assets pour diversification")
        
        if len(groups) < 3:
            recommendations.append("🏷️ Diversifier dans plus de groupes de cryptos")
        
        return recommendations[:3]  # Limiter à 3 recommandations
    
    def _load_historical_data(self) -> List[Dict[str, Any]]:
        """Charge les données historiques du portfolio"""
        try:
            if os.path.exists(self.historical_data_file):
                with open(self.historical_data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Erreur chargement données historiques: {e}")
        
        return []
    
    def _get_group_for_symbol(self, symbol: str) -> str:
        """
        Récupère le groupe taxonomique pour un symbole donné
        
        Args:
            symbol: Le symbole crypto (ex: "BTC", "ETH")
            
        Returns:
            Le groupe taxonomique (ex: "BTC", "ETH", "Stablecoins", "Others")
        """
        try:
            # Charger les aliases depuis le fichier de taxonomie
            taxonomy_file = os.path.join("data", "taxonomy.json")
            if not os.path.exists(taxonomy_file):
                return "Others"
                
            with open(taxonomy_file, 'r', encoding='utf-8-sig') as f:
                taxonomy_data = json.load(f)
            
            aliases = taxonomy_data.get("aliases", {})
            
            # Chercher le symbole dans les aliases (case insensitive)
            symbol_upper = symbol.upper()
            for alias, group in aliases.items():
                if alias.upper() == symbol_upper:
                    return group
            
            # Si pas trouvé, retourner "Others"
            return "Others"
            
        except Exception as e:
            logger.error(f"Erreur récupération groupe pour {symbol}: {e}")
            return "Others"

# Instance globale
portfolio_analytics = PortfolioAnalytics()