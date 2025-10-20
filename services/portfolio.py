"""
Service de portfolio analytics - calculs de performance, métriques, etc.
"""

from __future__ import annotations
import os
import json
import tempfile
from typing import Dict, List, Any, Literal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Timezone de référence pour tous les calculs temporels
TZ = ZoneInfo("Europe/Zurich")

def _atomic_json_dump(data: dict | list, path: Path | str) -> None:
    """
    Écriture atomique d'un fichier JSON pour éviter corruption.
    Utilise tempfile + os.replace (atomique sous Windows ≥ 10).

    Args:
        data: Données à sauvegarder
        path: Chemin du fichier cible
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent)
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)  # Atomique sous Windows ≥ 10
    except (OSError, PermissionError, ValueError) as e:
        # Nettoyer le fichier temporaire en cas d'erreur
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def _upsert_daily_snapshot(
    entries: list[dict],
    new_snap: dict,
    user_id: str,
    source: str
) -> None:
    """
    Insert ou update un snapshot pour un jour donné (évite doublons).
    Si un snapshot existe déjà le même jour civil (Europe/Zurich) pour ce
    (user_id, source), il est remplacé. Sinon, le nouveau est ajouté.

    Args:
        entries: Liste des snapshots existants (modifiée in-place)
        new_snap: Nouveau snapshot à insérer/mettre à jour
        user_id: ID utilisateur
        source: Source de données
    """
    new_date = datetime.fromisoformat(new_snap["date"]).astimezone(TZ).date()

    # Chercher s'il existe déjà un snapshot le même jour pour ce (user_id, source)
    for i in range(len(entries) - 1, -1, -1):
        entry = entries[i]
        if entry.get("user_id") == user_id and entry.get("source") == source:
            entry_date = datetime.fromisoformat(entry["date"]).astimezone(TZ).date()
            if entry_date == new_date:
                # Remplacer le snapshot existant
                entries[i] = new_snap
                logger.info(f"Snapshot mis à jour pour {user_id}/{source} le {new_date}")
                return

    # Aucun snapshot trouvé pour ce jour → ajouter
    entries.append(new_snap)
    logger.info(f"Nouveau snapshot ajouté pour {user_id}/{source} le {new_date}")


def _compute_anchor_ts(
    anchor: Literal["midnight", "prev_snapshot", "prev_close"] = "prev_snapshot",
    window: str = "24h",
    now: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    """
    Calcule le timestamp d'ancre pour comparaison P&L.

    Args:
        anchor: Type d'ancre ("midnight", "prev_snapshot", "prev_close")
        window: Fenêtre temporelle ("24h", "7d", "30d", "ytd")
        now: Timestamp actuel (défaut: maintenant en TZ)

    Returns:
        (anchor_ts, window_ts): Timestamps d'ancre et de fenêtre
    """
    now = (now or datetime.now(TZ)).astimezone(TZ)

    anchor_ts = None
    window_ts = None

    if anchor == "midnight":
        # Début du jour actuel (00:00 en TZ)
        anchor_ts = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif anchor == "prev_close":
        # Pour équités: fin de journée précédente (17:00 ou 22:00 selon marché)
        # Fallback: midnight pour crypto 24/7
        anchor_ts = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # else: prev_snapshot → anchor_ts reste None (sera dernier snapshot < now)

    # Calcul fenêtre temporelle
    if window == "24h":
        window_ts = now - timedelta(days=1)
    elif window == "7d":
        window_ts = now - timedelta(days=7)
    elif window == "30d":
        window_ts = now - timedelta(days=30)
    elif window == "ytd":
        # Year-to-date: début de l'année courante
        window_ts = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    return anchor_ts, window_ts


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
    
    def calculate_performance_metrics(
        self,
        current_data: Dict[str, Any],
        user_id: str = "demo",
        source: str = "cointracking",
        anchor: Literal["midnight", "prev_snapshot", "prev_close"] = "prev_snapshot",
        window: str = "24h"
    ) -> Dict[str, Any]:
        """
        Calcule les métriques de performance vs historique avec ancre configurable.

        Args:
            current_data: Données actuelles du portfolio
            user_id: ID de l'utilisateur pour filtrer l'historique
            source: Source de données pour filtrer l'historique
            anchor: Type d'ancre ("midnight", "prev_snapshot", "prev_close")
            window: Fenêtre temporelle ("24h", "7d", "30d", "ytd")

        Returns:
            Dict avec métriques de performance + métadonnées de comparaison
        """
        historical_data = self._load_historical_data(user_id=user_id, source=source)

        if not historical_data:
            return {
                "performance_available": False,
                "message": "Pas de données historiques disponibles",
                "days_tracked": 0
            }

        # Calculer l'ancre et la fenêtre
        anchor_ts, window_ts = _compute_anchor_ts(anchor=anchor, window=window)
        now = datetime.now(TZ)

        # Sélectionner le snapshot de base selon l'ancre
        base_snapshot = None

        if anchor_ts is not None:
            # Ancre temporelle fixe (midnight ou prev_close)
            # Chercher le snapshot le plus proche AVANT anchor_ts
            for snap in reversed(historical_data):
                snap_date = datetime.fromisoformat(snap.get("date")).astimezone(TZ)
                if snap_date <= anchor_ts:
                    base_snapshot = snap
                    break
        elif window_ts is not None:
            # Fenêtre temporelle relative
            # Chercher le snapshot le plus proche de window_ts
            for snap in reversed(historical_data):
                snap_date = datetime.fromisoformat(snap.get("date")).astimezone(TZ)
                if snap_date <= window_ts:
                    base_snapshot = snap
                    break
        else:
            # prev_snapshot: dernier snapshot avant maintenant
            base_snapshot = historical_data[-1] if historical_data else None

        if not base_snapshot:
            return {
                "performance_available": False,
                "message": f"Pas de snapshot trouvé pour anchor={anchor}, window={window}",
                "days_tracked": len(historical_data),
                "comparison": {
                    "anchor": anchor,
                    "window": window,
                    "available_snapshots": len(historical_data)
                }
            }

        current_value = current_data.get("total_value_usd", 0)
        historical_value = base_snapshot.get("total_value_usd", 0)

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
        base_date = datetime.fromisoformat(base_snapshot.get("date")).astimezone(TZ)
        days_tracked = (now - base_date).days
        hours_tracked = (now - base_date).total_seconds() / 3600

        # Performance annualisée (approximative)
        if days_tracked > 0:
            daily_return = (current_value / historical_value) ** (1 / days_tracked) - 1
            annualized_return = ((1 + daily_return) ** 365 - 1) * 100
        else:
            annualized_return = 0

        # Détection d'outlier (flux probable)
        suspected_flow = abs(percentage_change) > 30

        return {
            "performance_available": True,
            "current_value_usd": current_value,
            "historical_value_usd": historical_value,
            "absolute_change_usd": absolute_change,
            "percentage_change": percentage_change,
            "days_tracked": days_tracked,
            "hours_tracked": round(hours_tracked, 1),
            "annualized_return_estimate": annualized_return,
            "performance_status": "gain" if absolute_change > 0 else "loss" if absolute_change < 0 else "neutral",
            "suspected_flow": suspected_flow,
            "comparison": {
                "anchor": anchor,
                "window": window,
                "base_snapshot_at": base_snapshot.get("date"),
                "valuation_currency": "USD",
                "price_source": source
            },
            "historical_entries_count": len(historical_data)
        }
    
    def save_portfolio_snapshot(self, balances_data: Dict[str, Any], user_id: str = "demo", source: str = "cointracking") -> bool:
        """
        Sauvegarde un snapshot du portfolio pour suivi historique

        Args:
            balances_data: Données de balance actuelles
            user_id: ID de l'utilisateur
            source: Source de données

        Returns:
            True si sauvé avec succès
        """
        try:
            metrics = self.calculate_portfolio_metrics(balances_data)

            now = datetime.now(TZ)

            snapshot = {
                "date": now.isoformat(),
                "user_id": user_id,
                "source": source,
                "total_value_usd": metrics["total_value_usd"],
                "asset_count": metrics["asset_count"],
                "group_count": metrics["group_count"],
                "diversity_score": metrics["diversity_score"],
                "top_holding_symbol": metrics["top_holding"]["symbol"],
                "top_holding_percentage": metrics["top_holding"]["percentage"],
                "group_distribution": metrics["group_distribution"],
                # Métadonnées de valorisation
                "valuation_currency": "USD",
                "price_source": source,
                "pricing_timestamp": now.isoformat()
            }

            # Charger toutes les données existantes
            try:
                if os.path.exists(self.historical_data_file):
                    with open(self.historical_data_file, 'r', encoding='utf-8') as f:
                        all_historical_data = json.load(f)
                else:
                    all_historical_data = []
            except FileNotFoundError as e:
                logger.error(f"Fichier historique non trouvé: {e}")
                all_historical_data = []
            except PermissionError as e:
                logger.error(f"Permission refusée pour lire l'historique: {e}")
                all_historical_data = []
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erreur parsing JSON historique: {e}")
                all_historical_data = []

            # Ajouter ou mettre à jour snapshot (upsert journalier)
            _upsert_daily_snapshot(all_historical_data, snapshot, user_id, source)

            # Garder seulement les 365 derniers jours par (user_id, source)
            # Group by (user_id, source) and keep last 365 for each
            from collections import defaultdict
            grouped = defaultdict(list)
            for entry in all_historical_data:
                key = (entry.get('user_id', 'demo'), entry.get('source', 'cointracking'))
                grouped[key].append(entry)

            # Keep last 365 per group
            filtered_data = []
            for key, entries in grouped.items():
                # Sort by date
                sorted_entries = sorted(entries, key=lambda x: x.get('date', ''))
                # Keep last 365
                filtered_data.extend(sorted_entries[-365:])

            # Sauvegarder avec écriture atomique (anti-corruption)
            _atomic_json_dump(filtered_data, self.historical_data_file)

            logger.info(f"Portfolio snapshot sauvé ({metrics['total_value_usd']:.2f} USD) for user={user_id}, source={source}")
            return True

        except (OSError, PermissionError) as e:
            logger.error(f"Erreur I/O sauvegarde snapshot: {e}")
            return False
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Erreur données sauvegarde snapshot: {e}")
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
    
    def _load_historical_data(self, user_id: str = "demo", source: str = "cointracking") -> List[Dict[str, Any]]:
        """Charge les données historiques du portfolio filtrées par user et source"""
        try:
            if os.path.exists(self.historical_data_file):
                with open(self.historical_data_file, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                    # Filter by user_id and source
                    filtered = [
                        entry for entry in all_data
                        if entry.get('user_id') == user_id and entry.get('source') == source
                    ]
                    logger.info(f"Loaded {len(filtered)} historical entries for user={user_id}, source={source} (total={len(all_data)})")
                    return filtered
        except FileNotFoundError as e:
            logger.error(f"Fichier données historiques non trouvé: {e}")
        except PermissionError as e:
            logger.error(f"Permission refusée pour lire les données historiques: {e}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur parsing données historiques: {e}")

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

        except FileNotFoundError as e:
            logger.error(f"Fichier taxonomie non trouvé pour {symbol}: {e}")
            return "Others"
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur parsing taxonomie pour {symbol}: {e}")
            return "Others"
        except (KeyError, AttributeError) as e:
            logger.error(f"Erreur structure données taxonomie pour {symbol}: {e}")
            return "Others"

# Instance globale
portfolio_analytics = PortfolioAnalytics()