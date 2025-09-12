"""
Phase 2B2: Cross-Asset Correlation Analysis Engine

Moteur d'analyse de corrélations cross-asset temps réel avec :
- Calcul matrices de corrélation multi-timeframe optimisé
- Détection CORR_SPIKE (variations brutales) avec double critère  
- Clustering simple pour concentration detection
- Support PCA/Factor Analysis (préparé, dormant)
- Performance target: <50ms pour matrice 10x10
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
from collections import defaultdict, deque
import time

logger = logging.getLogger(__name__)

class ConcentrationMode(str, Enum):
    """Modes de détection de concentration"""
    CLUSTERING = "clustering"      # Clustering simple (corrélation > seuil)
    PCA = "pca"                   # PCA/Factor Analysis (dormant)
    HYBRID = "hybrid"             # Combine clustering + PCA (dormant)

@dataclass 
class CorrelationSpike:
    """Spike de corrélation détecté"""
    asset_pair: Tuple[str, str]
    timestamp: datetime
    correlation_before: float
    correlation_after: float
    relative_change: float       # % de variation relative
    absolute_change: float       # Variation absolue
    timeframe: str
    severity: str               # "minor", "major", "critical"

@dataclass
class ConcentrationCluster:
    """Cluster de concentration d'actifs"""
    cluster_id: str
    assets: Set[str]
    avg_correlation: float
    max_correlation: float
    risk_score: float           # 0-1, higher = more concentrated
    formation_time: datetime

@dataclass
class CrossAssetStatus:
    """Status global du système cross-asset"""
    timestamp: datetime
    total_assets: int
    correlation_matrix_shape: Tuple[int, int]
    avg_correlation: float
    max_correlation: float
    systemic_risk_score: float  # 0-1
    active_clusters: List[ConcentrationCluster]
    recent_spikes: List[CorrelationSpike]
    calculation_latency_ms: float

class CrossAssetCorrelationAnalyzer:
    """
    Analyseur de corrélations cross-asset temps réel
    
    Architecture optimisée pour performance <50ms sur matrice 10x10
    avec détection intelligente des spikes et clustering.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Configuration timeframes
        self.calculation_windows = config.get("calculation_windows", {
            "1h": 6,    # 6h de données pour corrélation 1h  
            "4h": 24,   # 24h pour corrélation 4h
            "1d": 168   # 7j pour corrélation daily
        })
        
        # Seuils corrélation
        self.correlation_thresholds = config.get("correlation_thresholds", {
            "low_risk": 0.6,
            "medium_risk": 0.75,
            "high_risk": 0.85,
            "systemic_risk": 0.95
        })
        
        # Configuration concentration  
        self.concentration_limits = config.get("concentration_limits", {
            "single_asset_max": 0.8,
            "cluster_max": 0.9
        })
        
        # Configuration CORR_SPIKE (double critère)
        self.spike_thresholds = config.get("spike_thresholds", {
            "relative_min": 0.15,  # ≥15% variation relative
            "absolute_min": 0.20   # ≥0.20 variation absolue
        })
        
        # Mode concentration (start simple)
        self.concentration_mode = ConcentrationMode(
            config.get("concentration_mode", "clustering")
        )
        
        # Caches et historiques
        self._correlation_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.calculation_windows.get("1d", 168))
        )
        self._last_correlation_matrices: Dict[str, np.ndarray] = {}
        self._active_clusters: List[ConcentrationCluster] = []
        self._spike_history: deque = deque(maxlen=100)
        
        # Métriques performance
        self._last_calculation_time = 0.0
        
        logger.info(f"CrossAssetCorrelationAnalyzer initialized: mode={self.concentration_mode}, "
                   f"windows={list(self.calculation_windows.keys())}")
    
    def update_price_data(self, assets_data: Dict[str, Dict[str, float]], timestamp: datetime = None):
        """
        Met à jour les données de prix pour tous les assets
        
        Args:
            assets_data: {"BTC": {"price": 45000, "volume": 1000000}, "ETH": {...}}
            timestamp: timestamp des données (défaut: now)
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Calculer returns pour chaque asset
        returns_data = {}
        for asset, data in assets_data.items():
            price = data.get("price", 0)
            if price > 0:
                # Calculer return vs prix précédent (simplifié pour MVP)
                history_key = f"{asset}_prices"
                if history_key in self._correlation_history and len(self._correlation_history[history_key]) > 0:
                    prev_price = self._correlation_history[history_key][-1]
                    returns_data[asset] = (price - prev_price) / prev_price if prev_price > 0 else 0.0
                else:
                    returns_data[asset] = 0.0
                
                # Stocker prix pour prochaine itération
                self._correlation_history[history_key].append(price)
        
        # Stocker returns avec timestamp
        for asset, return_value in returns_data.items():
            history_key = f"{asset}_returns"
            self._correlation_history[history_key].append({
                "timestamp": timestamp,
                "return": return_value,
                "asset": asset
            })
    
    def calculate_correlation_matrix(self, timeframe: str = "1h", assets: Optional[List[str]] = None) -> np.ndarray:
        """
        Calcule matrice de corrélation pour timeframe donné
        
        Performance target: <50ms pour matrice 10x10
        
        Args:
            timeframe: "1h", "4h", "1d"
            assets: liste d'assets (défaut: tous les assets disponibles)
            
        Returns:
            np.ndarray: matrice de corrélation NxN
        """
        start_time = time.time()
        
        window_hours = self.calculation_windows.get(timeframe, 6)
        cutoff_time = datetime.now() - timedelta(hours=window_hours)
        
        # Récupérer assets disponibles
        if assets is None:
            available_assets = set()
            for key in self._correlation_history.keys():
                if key.endswith("_returns"):
                    asset = key.replace("_returns", "")
                    available_assets.add(asset)
            assets = sorted(list(available_assets))
        
        if len(assets) < 2:
            logger.warning(f"Not enough assets for correlation matrix: {len(assets)}")
            return np.eye(len(assets)) if assets else np.array([])
        
        # Construire DataFrame des returns pour la fenêtre
        returns_data = []
        for asset in assets:
            history_key = f"{asset}_returns"
            if history_key in self._correlation_history:
                for entry in self._correlation_history[history_key]:
                    if entry["timestamp"] >= cutoff_time:
                        returns_data.append({
                            "timestamp": entry["timestamp"],
                            "asset": asset,
                            "return": entry["return"]
                        })
        
        if not returns_data:
            logger.warning(f"No returns data for timeframe {timeframe}")
            return np.eye(len(assets))
        
        # Convertir en DataFrame et calculer corrélations (optimisé)
        df = pd.DataFrame(returns_data)
        returns_matrix = df.pivot(index="timestamp", columns="asset", values="return")
        
        # Remplir NaN avec 0 et calculer matrice de corrélation
        returns_matrix = returns_matrix.fillna(0)
        correlation_matrix = returns_matrix.corr().values
        
        # Remplacer NaN par 0 (cas d'assets sans variance)
        correlation_matrix = np.nan_to_num(correlation_matrix, nan=0.0)
        
        # Cache et métriques
        self._last_correlation_matrices[timeframe] = correlation_matrix
        self._last_calculation_time = (time.time() - start_time) * 1000  # ms
        
        logger.debug(f"Correlation matrix calculated for {timeframe}: {correlation_matrix.shape} in {self._last_calculation_time:.1f}ms")
        
        return correlation_matrix
    
    def detect_correlation_spikes(self, timeframe: str = "1h", assets: Optional[List[str]] = None) -> List[CorrelationSpike]:
        """
        Détecte les spikes de corrélation avec double critère
        
        Critères: Δ≥15% variation relative ET Δ≥0.20 variation absolue
        
        Args:
            timeframe: timeframe à analyser
            assets: assets à considérer
            
        Returns:
            Liste des spikes détectés
        """
        current_matrix = self.calculate_correlation_matrix(timeframe, assets)
        
        if timeframe not in self._last_correlation_matrices:
            # Première évaluation, pas de comparaison possible
            return []
        
        previous_matrix = self._last_correlation_matrices.get(f"{timeframe}_previous")
        if previous_matrix is None or previous_matrix.shape != current_matrix.shape:
            # Sauvegarder matrice courante pour prochaine comparaison
            self._last_correlation_matrices[f"{timeframe}_previous"] = current_matrix.copy()
            return []
        
        spikes = []
        n_assets = current_matrix.shape[0]
        
        if assets is None:
            available_assets = [f"Asset_{i}" for i in range(n_assets)]  # Placeholder
        else:
            available_assets = assets[:n_assets]  # Assurer cohérence avec matrice
        
        # Analyser chaque paire d'assets
        for i in range(n_assets):
            for j in range(i + 1, n_assets):  # Éviter doublons et diagonale
                corr_before = previous_matrix[i, j]
                corr_after = current_matrix[i, j]
                
                if abs(corr_before) < 1e-6:  # Éviter division par 0
                    continue
                
                absolute_change = abs(corr_after - corr_before)
                relative_change = absolute_change / abs(corr_before)
                
                # Appliquer double critère
                meets_relative = relative_change >= self.spike_thresholds["relative_min"]
                meets_absolute = absolute_change >= self.spike_thresholds["absolute_min"]
                
                if meets_relative and meets_absolute:
                    # Déterminer sévérité
                    if absolute_change >= 0.40 or relative_change >= 0.50:
                        severity = "critical"
                    elif absolute_change >= 0.30 or relative_change >= 0.30:
                        severity = "major" 
                    else:
                        severity = "minor"
                    
                    spike = CorrelationSpike(
                        asset_pair=(available_assets[i], available_assets[j]),
                        timestamp=datetime.now(),
                        correlation_before=corr_before,
                        correlation_after=corr_after,
                        relative_change=relative_change,
                        absolute_change=absolute_change,
                        timeframe=timeframe,
                        severity=severity
                    )
                    
                    spikes.append(spike)
        
        # Sauvegarder matrice courante pour prochaine comparaison
        self._last_correlation_matrices[f"{timeframe}_previous"] = current_matrix.copy()
        
        # Ajouter à l'historique
        self._spike_history.extend(spikes)
        
        if spikes:
            logger.info(f"Detected {len(spikes)} correlation spikes in {timeframe}: "
                       f"{[s.severity for s in spikes]}")
        
        return spikes
    
    def detect_concentration_clusters(self, timeframe: str = "1h", assets: Optional[List[str]] = None) -> List[ConcentrationCluster]:
        """
        Détecte les clusters de concentration avec clustering simple
        
        Mode PCA/hybrid préparé mais dormant pour cette phase
        
        Args:
            timeframe: timeframe pour calcul corrélations
            assets: assets à analyser
            
        Returns:
            Liste des clusters détectés
        """
        correlation_matrix = self.calculate_correlation_matrix(timeframe, assets)
        
        if correlation_matrix.size == 0:
            return []
        
        n_assets = correlation_matrix.shape[0]
        if n_assets < 2:
            return []
        
        if assets is None:
            assets = [f"Asset_{i}" for i in range(n_assets)]
        
        clusters = []
        used_assets = set()
        
        # Clustering simple: regrouper assets avec corrélation > seuil
        cluster_threshold = self.concentration_limits["cluster_max"]
        
        for i in range(n_assets):
            if assets[i] in used_assets:
                continue
                
            # Trouver tous les assets corrélés à asset[i]
            cluster_assets = {assets[i]}
            correlations = []
            
            for j in range(n_assets):
                if i != j and assets[j] not in used_assets:
                    corr_value = abs(correlation_matrix[i, j])  # Valeur absolue de corrélation
                    if corr_value >= self.correlation_thresholds["high_risk"]:
                        cluster_assets.add(assets[j])
                        correlations.append(corr_value)
            
            # Créer cluster si au moins 2 assets
            if len(cluster_assets) >= 2:
                avg_correlation = np.mean(correlations) if correlations else 0
                max_correlation = max(correlations) if correlations else 0
                
                # Risk score basé sur taille cluster et corrélation moyenne
                size_factor = len(cluster_assets) / n_assets  # Proportion du portfolio
                correlation_factor = avg_correlation
                risk_score = min(1.0, size_factor * correlation_factor * 2)  # Cap à 1.0
                
                cluster = ConcentrationCluster(
                    cluster_id=f"cluster_{i}_{timeframe}",
                    assets=cluster_assets,
                    avg_correlation=avg_correlation,
                    max_correlation=max_correlation,
                    risk_score=risk_score,
                    formation_time=datetime.now()
                )
                
                clusters.append(cluster)
                used_assets.update(cluster_assets)
        
        # Mettre à jour cache des clusters actifs
        self._active_clusters = clusters
        
        if clusters:
            logger.info(f"Detected {len(clusters)} concentration clusters in {timeframe}: "
                       f"sizes={[len(c.assets) for c in clusters]}, "
                       f"risk_scores={[c.risk_score for c in clusters]}")
        
        return clusters
    
    def calculate_systemic_risk_score(self, timeframe: str = "1h", assets: Optional[List[str]] = None) -> float:
        """
        Calcule score de risque systémique global (0-1)
        
        Combine:
        - Corrélation moyenne du portfolio
        - Nombre de clusters de concentration  
        - Spikes récents de corrélation
        
        Args:
            timeframe: timeframe de référence
            assets: assets du portfolio
            
        Returns:
            float: score 0-1 (1 = risque systémique maximal)
        """
        correlation_matrix = self.calculate_correlation_matrix(timeframe, assets)
        
        if correlation_matrix.size == 0:
            return 0.0
        
        # Facteur 1: Corrélation moyenne (excluant diagonale)
        n = correlation_matrix.shape[0]
        if n <= 1:
            return 0.0
            
        # Extraire triangle supérieur (sans diagonale)
        upper_triangle = correlation_matrix[np.triu_indices(n, k=1)]
        avg_correlation = np.mean(np.abs(upper_triangle))
        
        # Normaliser: 0.5 corrélation = 0.5 score, 1.0 corrélation = 1.0 score
        correlation_factor = min(1.0, avg_correlation / 0.5)
        
        # Facteur 2: Clusters de concentration
        clusters = self.detect_concentration_clusters(timeframe, assets)
        if clusters:
            max_cluster_risk = max(c.risk_score for c in clusters)
            cluster_count_factor = min(1.0, len(clusters) / 3)  # Normaliser sur 3 clusters max
            concentration_factor = (max_cluster_risk + cluster_count_factor) / 2
        else:
            concentration_factor = 0.0
        
        # Facteur 3: Spikes récents (dernières 24h)
        recent_spikes = [s for s in self._spike_history 
                        if (datetime.now() - s.timestamp).total_seconds() < 86400]  # 24h
        
        if recent_spikes:
            # Poids selon sévérité
            severity_weights = {"critical": 1.0, "major": 0.7, "minor": 0.3}
            spike_score = sum(severity_weights.get(s.severity, 0.3) for s in recent_spikes)
            spike_factor = min(1.0, spike_score / 5)  # Normaliser sur 5 spikes critical
        else:
            spike_factor = 0.0
        
        # Score systémique final (moyenne pondérée)
        systemic_risk = (
            correlation_factor * 0.5 +    # 50% corrélation générale
            concentration_factor * 0.3 +   # 30% concentration clusters  
            spike_factor * 0.2             # 20% spikes récents
        )
        
        return min(1.0, systemic_risk)
    
    def get_status(self, timeframe: str = "1h", assets: Optional[List[str]] = None) -> CrossAssetStatus:
        """
        Retourne status complet du système cross-asset
        
        Args:
            timeframe: timeframe de référence
            assets: assets à analyser
            
        Returns:
            CrossAssetStatus avec toutes les métriques
        """
        # Calculs principaux
        correlation_matrix = self.calculate_correlation_matrix(timeframe, assets)
        clusters = self.detect_concentration_clusters(timeframe, assets)
        recent_spikes = [s for s in self._spike_history 
                        if (datetime.now() - s.timestamp).total_seconds() < 3600]  # 1h
        systemic_risk = self.calculate_systemic_risk_score(timeframe, assets)
        
        # Métriques matrice
        if correlation_matrix.size > 0:
            n = correlation_matrix.shape[0]
            upper_triangle = correlation_matrix[np.triu_indices(n, k=1)]
            avg_correlation = float(np.mean(np.abs(upper_triangle)))
            max_correlation = float(np.max(np.abs(upper_triangle)))
            total_assets = n
            matrix_shape = correlation_matrix.shape
        else:
            avg_correlation = 0.0
            max_correlation = 0.0
            total_assets = 0
            matrix_shape = (0, 0)
        
        return CrossAssetStatus(
            timestamp=datetime.now(),
            total_assets=total_assets,
            correlation_matrix_shape=matrix_shape,
            avg_correlation=avg_correlation,
            max_correlation=max_correlation,
            systemic_risk_score=systemic_risk,
            active_clusters=clusters,
            recent_spikes=recent_spikes,
            calculation_latency_ms=self._last_calculation_time
        )
    
    def get_top_correlated_pairs(self, timeframe: str = "1h", assets: Optional[List[str]] = None, 
                                top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Retourne les top N paires les plus corrélées
        
        Utile pour dashboard temps réel
        
        Args:
            timeframe: timeframe d'analyse
            assets: assets à considérer
            top_n: nombre de paires à retourner
            
        Returns:
            Liste de dict avec asset1, asset2, correlation, rank
        """
        correlation_matrix = self.calculate_correlation_matrix(timeframe, assets)
        
        if correlation_matrix.size == 0:
            return []
        
        n = correlation_matrix.shape[0]
        if n <= 1:
            return []
        
        if assets is None:
            assets = [f"Asset_{i}" for i in range(n)]
        
        # Extraire toutes les paires avec corrélations
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                corr_value = correlation_matrix[i, j]
                pairs.append({
                    "asset1": assets[i],
                    "asset2": assets[j],
                    "correlation": float(corr_value),
                    "abs_correlation": float(abs(corr_value))
                })
        
        # Trier par corrélation absolue (descending)
        pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
        
        # Retourner top N avec rang
        top_pairs = []
        for rank, pair in enumerate(pairs[:top_n], 1):
            top_pairs.append({
                "asset1": pair["asset1"],
                "asset2": pair["asset2"],
                "correlation": pair["correlation"],
                "abs_correlation": pair["abs_correlation"],
                "rank": rank
            })
        
        return top_pairs


# Fonction utilitaire pour initialisation
def create_cross_asset_analyzer(config: Dict[str, Any]) -> CrossAssetCorrelationAnalyzer:
    """Factory function pour créer analyzer avec config validée"""
    return CrossAssetCorrelationAnalyzer(config)