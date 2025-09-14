#!/usr/bin/env python3
"""
Script pour entraîner de nouveaux modèles ML pour le système crypto
- Modèle de détection de régime de marché (Bull/Bear/Sideways/Distribution)
- Modèles de prédiction de volatilité pour différents assets
"""

import sys
import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime, timedelta
import pickle
import math
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from torch.utils.data import DataLoader, TensorDataset
from torch.amp import autocast, GradScaler
import logging
import argparse
from typing import List, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Real data helpers (now that path is set)
from services.price_history import get_cached_history, PriceHistory

# Import the model classes from the service so torch.save can find them
from services.ml_pipeline_manager import RegimeClassifier, VolatilityPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GPU Configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"🔥 Using device: {device}")
if torch.cuda.is_available():
    logger.info(f"🚀 GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"💾 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

def enable_gpu_performance_mode():
    """Optimisations RTX 40xx: TF32, AMP-friendly, cudnn benchmark."""
    if not torch.cuda.is_available():
        return
    try:
        torch.set_float32_matmul_precision('high')  # active TF32
    except Exception:
        pass
    try:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    except Exception:
        pass
    # Performance over strict determinism
    torch.backends.cudnn.benchmark = True

# Activer le mode performance immédiatement si CUDA est disponible
enable_gpu_performance_mode()

# Model classes are now imported from services.ml_pipeline_manager

def set_deterministic_seeds(seed=42, deterministic=False):
    """Configure seeds; deterministic=False privilégie performance (4080)."""
    import torch  # Import local pour éviter les problèmes de portée
    import numpy as np
    
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    
    # Désactiver TorchDynamo pour éviter les erreurs mémoire
    try:
        import torch._dynamo
        torch._dynamo.config.suppress_errors = True
        torch._dynamo.config.disable = True
    except:
        pass
        
    if deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

def generate_synthetic_market_data(n_samples=5000, sequence_length=30):
    """Générer des données de marché synthétiques pour l'entraînement"""
    
    logger.info(f"Generating {n_samples} synthetic market samples...")
    
    # Reproductibilité légère (sans forcer determinism pour perf)
    set_deterministic_seeds(42, deterministic=False)
    
    # Simuler différents régimes de marché
    regimes = ['Bull', 'Bear', 'Sideways', 'Distribution']
    regime_to_id = {regime: idx for idx, regime in enumerate(regimes)}
    
    data = []
    
    for i in range(n_samples):
        # Choisir un régime aléatoirement avec des probabilités différentes
        regime_probs = [0.3, 0.2, 0.3, 0.2]  # Bull, Bear, Sideways, Distribution
        regime = np.random.choice(regimes, p=regime_probs)
        regime_id = regime_to_id[regime]
        
        # Générer des données selon le régime
        if regime == 'Bull':
            trend = np.random.normal(0.02, 0.01)  # Tendance haussière
            volatility = np.random.uniform(0.15, 0.35)  # Volatilité modérée
        elif regime == 'Bear':
            trend = np.random.normal(-0.02, 0.015)  # Tendance baissière
            volatility = np.random.uniform(0.25, 0.6)  # Haute volatilité
        elif regime == 'Sideways':
            trend = np.random.normal(0.0, 0.005)  # Pas de tendance
            volatility = np.random.uniform(0.1, 0.25)  # Faible volatilité
        else:  # Distribution
            trend = np.random.normal(-0.01, 0.02)  # Légèrement baissier
            volatility = np.random.uniform(0.4, 0.8)  # Très haute volatilité
        
        # Générer une séquence de prix
        prices = [100.0]  # Prix initial
        for _ in range(sequence_length):
            # Mouvement brownien géométrique simplifié
            daily_return = np.random.normal(trend, volatility)
            new_price = prices[-1] * (1 + daily_return)
            prices.append(max(new_price, 0.1))  # Éviter les prix négatifs
        
        prices = np.array(prices)
        
        # Calculer les features techniques
        returns = np.diff(prices) / prices[:-1]
        
        # Features pour la classification de régime
        features = {
            'price_change_1d': returns[-1] if len(returns) > 0 else 0,
            'price_change_7d': np.mean(returns[-7:]) if len(returns) >= 7 else 0,
            'volatility_7d': np.std(returns[-7:]) if len(returns) >= 7 else 0,
            'volatility_30d': np.std(returns) if len(returns) > 1 else 0,
            'rsi': calculate_rsi(prices[-14:]) if len(prices) >= 14 else 50,
            'price_position': (prices[-1] - np.min(prices)) / (np.max(prices) - np.min(prices)) if np.max(prices) > np.min(prices) else 0.5,
            'trend_strength': np.corrcoef(range(len(prices)), prices)[0, 1] if len(prices) > 1 else 0,
            'volume_trend': np.random.uniform(0.5, 2.0),  # Volume simulé
            'momentum': returns[-1] - np.mean(returns[-5:]) if len(returns) >= 5 else 0,
            'max_drawdown': calculate_max_drawdown(prices)
        }
        
        # Séquence pour la prédiction de volatilité (LSTM)
        # Génère une feature par point de la série de rendements, en utilisant
        # uniquement l'historique disponible jusqu'à j (pas de fuite du futur).
        vol_sequence = []
        for j in range(len(returns)):
            vol_features = [
                returns[j],
                np.std(returns[max(0, j-7):j+1]),  # Volatilité historique
                np.mean(returns[max(0, j-7):j+1]),  # Rendement moyen
                abs(returns[j]),  # Volatilité absolue
                1 if returns[j] > 0 else 0  # Direction
            ]
            vol_sequence.append(vol_features)

        if len(vol_sequence) >= 30:  # Assez de données pour une séquence de 30 points
            data.append({
                'regime_features': list(features.values()),
                'regime_label': regime_id,
                'volatility_sequence': vol_sequence[-30:],  # 30 derniers points pour LSTM
                'actual_volatility': volatility,
                'regime_name': regime
            })
    
    logger.info(f"Generated {len(data)} valid samples")
    return data

def generate_real_market_data(
    symbols: List[str],
    days: int = 400,
    sequence_length: int = 30,
    include_btc_features: bool = True,
    ret30_thr: float = 0.05,
    vol_pct: int = 70,
    use_regime_proba: bool = False,
    regime_model: Optional[nn.Module] = None,
    regime_scaler: Optional[StandardScaler] = None,
    regime_features_names: Optional[List[str]] = None,
    temp_T: float = 1.0,
):
    """Génère des échantillons à partir de données réelles OHLC (close 1d) via le cache historique.

    - Construit des features de régime analogues au synthétique
    - Construit des séquences de volatilité (30 pas, 5 features)
    - Cible volatilité: réalisation sur 7 jours à horizon futur (forward 7d std)
    """
    logger.info(f"Generating real market samples for {symbols} over {days}d...")

    ph = PriceHistory()
    data = []

    # Préparer BTC pour features de référence
    btc_returns_ref = None
    if include_btc_features:
        try:
            import asyncio
            btc_hist = get_cached_history('BTC', days=days) or []
            if not btc_hist:
                asyncio.run(ph.download_historical_data('BTC', days=days))  # type: ignore
                btc_hist = get_cached_history('BTC', days=days) or []
            if btc_hist:
                btc_prices = np.array([px for ts, px in sorted(btc_hist, key=lambda x: x[0])], dtype=float)
                btc_returns_ref = np.diff(btc_prices) / btc_prices[:-1]
        except Exception:
            btc_returns_ref = None

    for symbol in symbols:
        # Assurer que l'historique existe (télécharge si nécessaire)
        hist = get_cached_history(symbol, days=days)
        if not hist:
            try:
                import asyncio
                asyncio.run(ph.download_historical_data(symbol, days=days))
            except Exception as e:
                logger.warning(f"Download failed for {symbol}: {e}")
        hist = get_cached_history(symbol, days=days) or []
        if len(hist) < sequence_length + 40:
            logger.warning(f"Not enough real data for {symbol}: {len(hist)} points")
            continue

        # Convert to arrays sorted by time
        hist = sorted(hist, key=lambda x: x[0])
        prices = np.array([px for ts, px in hist], dtype=float)
        returns = np.diff(prices) / prices[:-1]

        # Precompute rolling stats
        def rolling_std(a, w):
            if len(a) < w:
                return np.array([])
            out = np.array([np.std(a[i-w+1:i+1]) for i in range(w-1, len(a))])
            return out
        def rolling_mean(a, w):
            if len(a) < w:
                return np.array([])
            out = np.array([np.mean(a[i-w+1:i+1]) for i in range(w-1, len(a))])
            return out

        # Forward 7d realized volatility as target (align with current day index)
        fwd_window = 7
        realized_vol = np.array([
            np.std(returns[i+1:i+1+fwd_window]) if i+1+fwd_window <= len(returns) else np.nan
            for i in range(len(returns))
        ])

        # Heuristic regime labeling per day window of 30d
        for end_idx in range(sequence_length, len(returns)-fwd_window-1):
            window_returns = returns[end_idx-sequence_length:end_idx]
            if len(window_returns) < sequence_length:
                continue

            # Regime features (10) akin to synthetic
            r_1d = window_returns[-1]
            r_7d = np.mean(window_returns[-7:])
            vol_7d = np.std(window_returns[-7:])
            vol_30d = np.std(window_returns)
            rsi_val = calculate_rsi(prices[end_idx-sequence_length+1:end_idx+1]) if end_idx+1 <= len(prices) else 50
            pos = (prices[end_idx] - np.min(prices[end_idx-sequence_length:end_idx+1]))
            denom = (np.max(prices[end_idx-sequence_length:end_idx+1]) - np.min(prices[end_idx-sequence_length:end_idx+1]))
            price_pos = (pos / denom) if denom > 0 else 0.5
            try:
                trend_strength = np.corrcoef(np.arange(sequence_length), prices[end_idx-sequence_length+1:end_idx+1])[0, 1]
            except Exception:
                trend_strength = 0.0
            volume_trend = 1.0  # placeholder (no volume in cache)
            momentum = r_1d - (np.mean(window_returns[-5:]) if len(window_returns) >= 5 else 0)
            mdd = calculate_max_drawdown(prices[end_idx-sequence_length:end_idx+1])

            regime_features = [
                r_1d, r_7d, vol_7d, vol_30d, rsi_val, price_pos, trend_strength, volume_trend, momentum, mdd
            ]

            # Regime label heuristic (corrigé)
            ret_30 = np.sum(window_returns)
            vol_q = vol_30d
            # Historique de vol rolling 30j (uniquement passé)
            hist_roll_vol = rolling_std(returns[:end_idx], 30)
            # Fenêtre de référence (jusqu'à 180 derniers points si dispo)
            ref_vol = hist_roll_vol[-180:] if len(hist_roll_vol) >= 180 else hist_roll_vol
            pct = max(50, min(95, int(vol_pct)))
            vol_thresh = np.percentile(ref_vol, pct) if len(ref_vol) > 0 else np.std(returns[:end_idx])
            thr = float(ret30_thr)
            bull = (ret_30 > thr) and (trend_strength > 0)
            bear = (ret_30 < -thr) and (trend_strength < 0)
            high_vol = vol_q >= vol_thresh
            side = (abs(ret_30) <= thr - 0.01) and (not high_vol)
            if bull:
                regime_label, regime_name = 0, 'Bull'
            elif bear:
                regime_label, regime_name = 1, 'Bear'
            elif side:
                regime_label, regime_name = 2, 'Sideways'
            else:
                regime_label, regime_name = 3, 'Distribution'

            # Probabilités de régime prédictives (teacher-student)
            proba_reg = None
            if use_regime_proba and (regime_model is not None) and (regime_scaler is not None):
                try:
                    feat_vec = np.array([
                        r_1d, r_7d, vol_7d, vol_30d, rsi_val, price_pos, trend_strength, volume_trend, momentum, mdd
                    ], dtype=np.float32).reshape(1, -1)
                    feat_scaled = regime_scaler.transform(feat_vec)
                    regime_model.eval()
                    with torch.no_grad():
                        logits = regime_model(torch.from_numpy(feat_scaled).float())
                        logits = logits / max(1e-6, float(temp_T))
                        proba = torch.softmax(logits, dim=1).cpu().numpy()[0]
                    proba_reg = proba.tolist()
                except Exception:
                    proba_reg = None

            # Volatility sequence features (30,12 [+2 si BTC]): 7 de base + 4 canaux régime (proba/ou one-hot) + 1 prev_realized_vol [+ corr/beta BTC]
            vol_sequence = []
            seq_returns = window_returns
            # Aligner BTC returns à la longueur locale si disponible
            if include_btc_features and btc_returns_ref is not None:
                if len(btc_returns_ref) >= len(returns):
                    btc_tail = btc_returns_ref[-len(returns):]
                else:
                    # Si trop court, répéter le dernier (fallback simple)
                    pad = len(returns) - len(btc_returns_ref)
                    btc_tail = np.concatenate([np.full(pad, btc_returns_ref[0] if len(btc_returns_ref) else 0.0), btc_returns_ref])
            else:
                btc_tail = None
            for j in range(sequence_length):
                rr = seq_returns[j]
                hist_slice = seq_returns[max(0, j-7):j+1]
                hist_slice_30 = seq_returns[:j+1]
                std7 = np.std(hist_slice) if len(hist_slice) > 0 else 0.0
                std30_sofar = np.std(hist_slice_30) if len(hist_slice_30) > 0 else 0.0
                ratio = (std7 / (std30_sofar + 1e-8)) if std30_sofar > 0 else 0.0
                # Régime: probas prédictives (si dispo), sinon one-hot heuristique
                if proba_reg is not None and len(proba_reg) == 4:
                    reg_probs = proba_reg
                else:
                    reg_probs = [
                        1 if regime_label == 0 else 0,
                        1 if regime_label == 1 else 0,
                        1 if regime_label == 2 else 0,
                        1 if regime_label == 3 else 0,
                    ]
                # Volatilité réalisée de la veille comme feature globale (répétée)
                prev_rv = realized_vol[end_idx-1] if end_idx-1 >= 0 and np.isfinite(realized_vol[end_idx-1]) else 0.0
                # Corrélation et beta vs BTC (fenêtre jusqu'à j)
                corr_btc = 0.0
                beta_btc = 0.0
                if btc_tail is not None:
                    x = seq_returns[max(0, j-29):j+1]
                    y = btc_tail[end_idx-sequence_length+1+max(0, j-29): end_idx-sequence_length+1+j+1]
                    if len(x) == len(y) and len(x) >= 5:
                        try:
                            corr_btc = float(np.corrcoef(x, y)[0, 1])
                            beta_btc = float(np.cov(x, y)[0, 1] / (np.var(y) + 1e-8))
                        except Exception:
                            pass
                vol_sequence.append([
                    rr,
                    std7,
                    np.mean(hist_slice) if len(hist_slice) > 0 else 0.0,
                    abs(rr),
                    1 if rr > 0 else 0,
                    std30_sofar,
                    ratio,
                    *reg_probs,
                    prev_rv,
                    *( [corr_btc, beta_btc] if btc_tail is not None else [] )
                ])

            # Target realized volatility next 7d (non clampée)
            target_vol = realized_vol[end_idx]
            if not np.isfinite(target_vol):
                continue
            target_vol = float(target_vol)

            data.append({
                'regime_features': regime_features,
                'regime_label': regime_label,
                'volatility_sequence': vol_sequence,
                'actual_volatility': target_vol,
                'regime_name': regime_name,
                'symbol': symbol
            })

    logger.info(f"Generated {len(data)} real samples")
    return data

def calculate_rsi(prices, period=14):
    """Calculer l'indice de force relative (RSI)"""
    if len(prices) < period + 1:
        return 50.0
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_max_drawdown(prices):
    """Calculer le drawdown maximum"""
    if len(prices) < 2:
        return 0.0
    
    peak = np.maximum.accumulate(prices)
    drawdown = (prices - peak) / peak
    return np.min(drawdown)

def train_regime_model(data, epochs: int = 200, patience: int = 15):
    """Entraîner le modèle de détection de régime"""
    
    logger.info("Training regime classification model...")
    
    # Préparer les données
    X = np.array([sample['regime_features'] for sample in data])
    y = np.array([sample['regime_label'] for sample in data])
    
    # Normalisation
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Division train/val/test temporelle (évite la fuite temporelle)
    n = len(X_scaled)
    train_end = int(0.6 * n)
    val_end = int(0.8 * n)
    X_train, y_train = X_scaled[:train_end], y[:train_end]
    X_val, y_val = X_scaled[train_end:val_end], y[train_end:val_end]
    X_test, y_test = X_scaled[val_end:], y[val_end:]
    
    # Tenseurs CPU; on transfère en GPU dans la boucle (non_blocking)
    X_train_tensor = torch.from_numpy(X_train).float()
    y_train_tensor = torch.from_numpy(y_train).long()
    X_val_tensor = torch.from_numpy(X_val).float().to(device)
    y_val_tensor = torch.from_numpy(y_val).long().to(device)
    X_test_tensor = torch.from_numpy(X_test).float().to(device)
    y_test_tensor = torch.from_numpy(y_test).long().to(device)
    
    # DataLoader CPU -> GPU (pinned memory accélère H2D sur RTX 40xx)
    # Utiliser un échantillonnage pondéré pour atténuer le déséquilibre de classes
    from torch.utils.data import WeightedRandomSampler
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    workers = 0  # éviter les erreurs DLL sous Windows
    batch_size_regime = min(512, max(128, len(X_train)))
    class_counts = np.bincount(y_train, minlength=4)
    class_counts = np.maximum(class_counts, 1)  # éviter division par zéro
    class_weights = 1.0 / class_counts
    sample_weights = class_weights[y_train]
    sampler = WeightedRandomSampler(weights=torch.from_numpy(sample_weights).float(),
                                    num_samples=len(y_train), replacement=True)
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size_regime, shuffle=False,
        sampler=sampler, pin_memory=True, num_workers=workers
    )
    
    # Modèle sur GPU
    model = RegimeClassifier(input_size=X.shape[1], hidden_sizes=[128, 64], num_classes=4).to(device)
    # Désactiver torch.compile pour éviter les erreurs mémoire
    # if hasattr(torch, 'compile') and device.type == 'cuda':
    #     try:
    #         model = torch.compile(model)
    #         compiled_regime = True
    #     except Exception:
    #         compiled_regime = False
    # else:
    #     compiled_regime = False
    compiled_regime = False
    # Perte pondérée + label smoothing (renforce minoritaires)
    cw = torch.tensor((class_weights / class_weights.mean()).astype(np.float32), device=device)
    criterion = nn.CrossEntropyLoss(weight=cw, label_smoothing=0.05)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
    # Préférer BF16 si supporté sur RTX 4080 (plus stable que FP16)
    try:
        bf16_supported = bool(getattr(torch.cuda, 'is_bf16_supported', lambda: False)()) if device.type == 'cuda' else False
    except Exception:
        bf16_supported = False
    amp_dtype = torch.bfloat16 if (device.type == 'cuda' and bf16_supported) else torch.float16
    amp_scaler = GradScaler('cuda', enabled=(device.type == 'cuda' and amp_dtype == torch.float16))
    
    logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Entraînement avec early stopping
    best_val_acc = -float('inf')
    no_improve = 0
    # Initialiser pour garantir un état valide même sans amélioration
    best_model_state = model.state_dict().copy()
    
    for epoch in range(epochs):
        # Training
        model.train()
        total_loss = 0
        num_batches = 0
        
        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with autocast('cuda', enabled=(device.type == 'cuda'), dtype=amp_dtype):
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
            if amp_scaler.is_enabled():
                amp_scaler.scale(loss).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                amp_scaler.step(optimizer)
                amp_scaler.update()
            else:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val_tensor)
            val_loss = criterion(val_outputs, y_val_tensor)
            _, val_predicted = torch.max(val_outputs, 1)
            val_accuracy = accuracy_score(y_val, val_predicted.cpu().numpy())
        
        scheduler.step(val_loss)
        
        # Early stopping sur accuracy validation
        if val_accuracy > best_val_acc:
            best_val_acc = val_accuracy
            best_model_state = model.state_dict().copy()
            no_improve = 0
        else:
            no_improve += 1
            
        if no_improve >= patience:
            logger.info(f"Early stopping at epoch {epoch+1}")
            break
        
        if (epoch + 1) % 20 == 0:
            avg_loss = total_loss / num_batches
            logger.info(f'Epoch [{epoch+1}/{epochs}], Train Loss: {avg_loss:.4f}, Val Loss: {val_loss:.4f}, Val Acc: {val_accuracy:.4f}')
    
    # Charger le meilleur modèle et évaluer
    model.load_state_dict(best_model_state)
    model.eval()
    
    with torch.no_grad():
        test_outputs = model(X_test_tensor)
        _, predicted = torch.max(test_outputs, 1)
        accuracy = accuracy_score(y_test, predicted.cpu().numpy())
        
    # Rapport détaillé (gérer classes manquantes en réel)
    classes = ["Bull", "Bear", "Sideways", "Distribution"]
    all_labels = [0, 1, 2, 3]
    report = classification_report(
        y_test,
        predicted.cpu().numpy(),
        labels=all_labels,
        target_names=classes,
        zero_division=0
    )
    cm = confusion_matrix(y_test, predicted.cpu().numpy(), labels=all_labels)
    
    # Calibration température (grid-search simple sur val)
    with torch.no_grad():
        val_logits = model(X_val_tensor)
    Ts = np.linspace(0.5, 3.0, 26)
    best_T = 1.0
    best_nll = float('inf')
    for T in Ts:
        scaled = val_logits / float(T)
        nll = nn.CrossEntropyLoss()(scaled, y_val_tensor).item()
        if nll < best_nll:
            best_nll = nll
            best_T = float(T)

    logger.info(f'Regime model - Best Val Acc: {best_val_acc:.4f}, Test Acc: {accuracy:.4f}, Temp T: {best_T:.2f}')
    logger.info(f'Classification Report:\n{report}')
    logger.info(f'Confusion Matrix:\n{cm}')
    
    # Déplacer le modèle sur CPU pour la sauvegarde
    model = model.cpu()
    
    # Métadonnées enrichies
    metadata = {
        "model_type": "regime_classifier",
        "version": "2.0.0",
        "accuracy": float(accuracy),
        "best_val_accuracy": float(best_val_acc),
        "classes": ["Bull", "Bear", "Sideways", "Distribution"],
        "input_features": [
            "price_change_1d", "price_change_7d", "volatility_7d", "volatility_30d",
            "rsi", "price_position", "trend_strength", "volume_trend", 
            "momentum", "max_drawdown"
        ],
        "trained_at": datetime.now().isoformat(),
        "pytorch_version": torch.__version__,
        "numpy_version": np.__version__,
        "data_source": "synthetic",
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "test_samples": len(X_test),
        "early_stopped": no_improve >= patience,
        "seed": 42,
        "amp": device.type == 'cuda',
        "tf32": bool(getattr(torch.backends.cuda.matmul, 'allow_tf32', False)) if device.type == 'cuda' else False,
        "compiled": compiled_regime,
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "temperature_T": best_T
    }
    
    return model, scaler, metadata['input_features'], metadata

def train_volatility_model(data, symbol="BTC", epochs: int = 200, patience: int = 15, hidden_override: int = 0, log_vol: bool = False):
    """Entraîner le modèle de prédiction de volatilité"""
    
    logger.info(f"Training volatility prediction model for {symbol}...")
    
    # Préparer les séquences
    sequences = []
    targets = []
    
    for sample in data:
        # En mode réel, filtrer par symbole pour entraîner un modèle spécifique
        if 'symbol' in sample and sample['symbol'] != symbol:
            continue
        if len(sample['volatility_sequence']) >= 30:
            seq = np.array(sample['volatility_sequence'])
            if len(seq) >= 30:
                sequences.append(seq[-30:])  # 30 derniers points (harmonisé)
                # Normaliser/clipper la volatilité cible entre 0 et 1
                targets.append(min(sample['actual_volatility'], 1.0))
    
    if len(sequences) < 100:
        logger.warning(f"Not enough data for volatility model: {len(sequences)} sequences")
        return None, None, None, None
    
    X = np.array(sequences)
    y = np.array(targets)
    
    logger.info(f"Volatility model data shape: X={X.shape}, y={y.shape}")
    
    # Division train/val/test AVANT normalisation (split temporel, pas aléatoire)
    n = len(X)
    train_end = int(0.6 * n)
    val_end = int(0.8 * n)
    X_train, y_train = X[:train_end], y[:train_end]
    X_val, y_val = X[train_end:val_end], y[train_end:val_end]
    X_test, y_test = X[val_end:], y[val_end:]

    # Option: transformer la cible en log-vol
    y_train_t = np.log1p(y_train) if log_vol else y_train
    y_val_t = np.log1p(y_val) if log_vol else y_val
    y_test_t = np.log1p(y_test) if log_vol else y_test
    # Mise à l'échelle par percentiles (p10-p90)
    p10 = float(np.percentile(y_train_t, 10))
    p90 = float(np.percentile(y_train_t, 90))
    scale = max(1e-6, (p90 - p10))
    def scale_y(arr):
        return np.clip((arr - p10) / scale, 0.0, 1.0)
    y_train_scaled = scale_y(y_train_t)
    y_val_scaled = scale_y(y_val_t)
    y_test_scaled = scale_y(y_test_t)
    
    # Normalisation par feature (5 features) - fit sur train uniquement
    scaler = StandardScaler()
    # Reshape pour normaliser par feature: (n_samples * seq_len, n_features)
    X_train_reshaped = X_train.reshape(-1, X_train.shape[2])
    scaler.fit(X_train_reshaped)
    
    # Appliquer à tous les splits
    X_train_scaled = scaler.transform(X_train.reshape(-1, X_train.shape[2])).reshape(X_train.shape)
    X_val_scaled = scaler.transform(X_val.reshape(-1, X_val.shape[2])).reshape(X_val.shape)
    X_test_scaled = scaler.transform(X_test.reshape(-1, X_test.shape[2])).reshape(X_test.shape)
    
    # Conversion CPU; transfert GPU dans boucle
    X_train_tensor = torch.from_numpy(X_train_scaled).float()
    y_train_tensor = torch.from_numpy(y_train_scaled).float().unsqueeze(1)
    X_val_tensor = torch.from_numpy(X_val_scaled).float().to(device)
    y_val_tensor = torch.from_numpy(y_val_scaled).float().unsqueeze(1).to(device)
    X_test_tensor = torch.from_numpy(X_test_scaled).float().to(device)
    y_test_tensor = torch.from_numpy(y_test_scaled).float().unsqueeze(1).to(device)
    
    # DataLoader CPU -> GPU (pinned memory)
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    workers = 0
    batch_size_vol = min(1024, max(128, len(X_train)))
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size_vol, shuffle=True,
        pin_memory=True, num_workers=workers
    )
    
    # Modèle optimisé sur GPU avec architecture adaptée
    hidden_size = hidden_override if hidden_override and hidden_override > 0 else max(64, min(256, X.shape[2] * 8))
    model = VolatilityPredictor(input_size=X.shape[2], hidden_size=hidden_size, num_layers=2).to(device)
    # Désactiver torch.compile pour éviter les erreurs mémoire
    compiled_vol = False
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
    # AMP: préférer BF16 si supporté
    try:
        bf16_supported = bool(getattr(torch.cuda, 'is_bf16_supported', lambda: False)()) if device.type == 'cuda' else False
    except Exception:
        bf16_supported = False
    amp_dtype = torch.bfloat16 if (device.type == 'cuda' and bf16_supported) else torch.float16
    amp_scaler = GradScaler('cuda', enabled=(device.type == 'cuda' and amp_dtype == torch.float16))
    
    logger.info(f"Volatility model parameters: {sum(p.numel() for p in model.parameters()):,}")
    logger.info(f"Target scaling p10={p10:.6f}, p90={p90:.6f}, scale={scale:.6f}, log_vol={log_vol}")
    
    # Entraînement avec early stopping
    best_val_loss = float('inf')
    no_improve = 0
    
    for epoch in range(epochs):
        # Training
        model.train()
        total_loss = 0
        num_batches = 0
        
        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with autocast('cuda', enabled=(device.type == 'cuda'), dtype=amp_dtype):
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
            if amp_scaler.is_enabled():
                amp_scaler.scale(loss).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                amp_scaler.step(optimizer)
                amp_scaler.update()
            else:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val_tensor)
            val_loss = criterion(val_outputs, y_val_tensor)
        
        scheduler.step(val_loss)
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            no_improve = 0
        else:
            no_improve += 1
            
        if no_improve >= patience:
            logger.info(f"Early stopping at epoch {epoch+1}")
            break
        
        if (epoch + 1) % 20 == 0:
            avg_loss = total_loss / num_batches
            logger.info(f'Epoch [{epoch+1}/{epochs}], Train Loss: {avg_loss:.6f}, Val Loss: {val_loss:.6f}')
    
    # Charger le meilleur modèle
    model.load_state_dict(best_model_state)
    
    # Évaluation finale
    model.eval()
    with torch.no_grad():
        test_outputs = model(X_test_tensor)
        test_loss = criterion(test_outputs, y_test_tensor)
        
        # Calcul du R²
        ss_res = torch.sum((y_test_tensor - test_outputs) ** 2)
        ss_tot = torch.sum((y_test_tensor - torch.mean(y_test_tensor)) ** 2)
        r2 = 1 - (ss_res / ss_tot)
        
    # Diagnostics par segments temporels sur le jeu de test
    seg_metrics = []
    k = 4
    n_test = X_test_tensor.shape[0]
    seg_len = max(1, n_test // k)
    with torch.no_grad():
        for i in range(k):
            start = i * seg_len
            end = n_test if i == k - 1 else (i + 1) * seg_len
            if start >= end:
                continue
            y_seg = y_test_tensor[start:end]
            y_pred_seg = model(X_test_tensor[start:end])
            mse_seg = torch.mean((y_seg - y_pred_seg) ** 2)
            ss_res_seg = torch.sum((y_seg - y_pred_seg) ** 2)
            ss_tot_seg = torch.sum((y_seg - torch.mean(y_seg)) ** 2)
            r2_seg = 1 - (ss_res_seg / (ss_tot_seg + 1e-12))
            seg_metrics.append({
                'segment': i + 1,
                'start': int(start),
                'end': int(end),
                'mse': float(mse_seg.item()),
                'r2': float(r2_seg.item()),
            })

    logger.info(f'Volatility model - Best Val MSE: {best_val_loss:.6f}, Test MSE: {test_loss:.6f}, R²: {r2:.4f}')
    logger.info(f'Segment diagnostics: {seg_metrics}')
    
    # Déplacer le modèle sur CPU pour la sauvegarde  
    model = model.cpu()
    
    # Métadonnées enrichies et compatibles avec le pipeline manager
    metadata = {
        "symbol": symbol,
        "model_type": "volatility_predictor", 
        "version": "2.0.0",
        "test_mse": float(test_loss.item()),
        "r2_score": float(r2.item()),
        "sequence_length": X.shape[1],
        "input_features": [
            "price_return",
            "historical_volatility_7",
            "avg_return_7",
            "absolute_return",
            "direction",
            "historical_volatility_30_sofar",
            "vol_ratio_7_over_30",
            "regime_bull",
            "regime_bear",
            "regime_sideways",
            "regime_distribution",
            "prev_realized_vol_7d",
        ],
        "trained_at": datetime.now().isoformat(),
        "pytorch_version": torch.__version__,
        "numpy_version": np.__version__,
        "scaler_type": "standard_per_feature",
        "input_size": X.shape[2],
        "hidden_size": hidden_size,
        "num_layers": 2,
        "data_source": "real" if any(('symbol' in s) for s in data) else "synthetic",
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "test_samples": len(X_test),
        "best_val_mse": float(best_val_loss.item()),
        "early_stopped": no_improve >= patience,
        "seed": 42,
        "amp": device.type == 'cuda',
        "tf32": bool(getattr(torch.backends.cuda.matmul, 'allow_tf32', False)) if device.type == 'cuda' else False,
        "compiled": compiled_vol,
        "target_scaling": "percentile_10_90",
        "target_p10": p10,
        "target_p90": p90,
        "target_transform": "log1p" if log_vol else "none",
        "test_segments": seg_metrics
    }
    
    return model, scaler, None, metadata

def save_models(
    symbols=None,
    train_regime=True,
    samples=10000,
    real_data: bool = False,
    days: int = 400,
    epochs_regime: int = 200,
    patience_regime: int = 15,
    epochs_vol: int = 200,
    patience_vol: int = 15,
    hidden_vol: int = 0,
    min_r2: float = -1.0,
    ret30_thr: float = 0.05,
    vol_pct: int = 70,
):
    """Entraîner et sauvegarder les nouveaux modèles"""
    
    # Créer les dossiers
    models_path = Path(__file__).parent.parent / "models"
    regime_path = models_path / "regime"
    volatility_path = models_path / "volatility"
    
    regime_path.mkdir(parents=True, exist_ok=True)
    volatility_path.mkdir(parents=True, exist_ok=True)
    
    # Générer les données d'entraînement
    if real_data:
        if not symbols:
            symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'LINK', 'AVAX']
        logger.info(f"Generating real market samples for {symbols} over {days}d...")
        data = generate_real_market_data(symbols, days=days, sequence_length=30, include_btc_features=True)
    else:
        logger.info(f"Generating {samples} training samples...")
        data = generate_synthetic_market_data(n_samples=samples)
    
    if train_regime:
        # 1. Entraîner le modèle de régime
        logger.info("\n=== Training Regime Classification Model ===")
        regime_model, scaler, features, metadata = train_regime_model(data, epochs=epochs_regime, patience=patience_regime)
        
        # Sauvegarder le modèle de régime
        torch.save(regime_model, regime_path / "regime_neural_best.pth", _use_new_zipfile_serialization=False)
        
        import joblib
        joblib.dump(scaler, regime_path / "regime_scaler.pkl")
        
        with open(regime_path / "regime_features.pkl", 'wb') as f:
            pickle.dump(features, f)
            
        with open(regime_path / "regime_metadata.pkl", 'wb') as f:
            pickle.dump(metadata, f)
        
        logger.info(f"✅ Regime model saved to {regime_path}")
    
    # 2. Entraîner les modèles de volatilité pour les symboles sélectionnés
    if symbols is None:
        symbols = ['BTC', 'ETH', 'LINK', 'ADA', 'SOL', 'DOGE', 'AVAX']
    
    # Préparer le dataset pour la vol: si réel, utiliser les probas de régime prédictives
    if real_data:
        try:
            T = float(metadata.get('temperature_T', 1.0)) if train_regime else 1.0
        except Exception:
            T = 1.0
        data_for_vol = generate_real_market_data(
            symbols, days=days, sequence_length=30, include_btc_features=True,
            ret30_thr=ret30_thr, vol_pct=vol_pct, use_regime_proba=True,
            regime_model=regime_model if train_regime else None,
            regime_scaler=scaler if train_regime else None,
            regime_features_names=features if train_regime else None,
            temp_T=T,
        )
    else:
        data_for_vol = data

    logger.info(f"\n=== Training Volatility Models for {symbols} ===")
    for symbol in symbols:
        logger.info(f"\nTraining volatility model for {symbol}...")
        vol_model, vol_scaler, _, vol_metadata = train_volatility_model(
            data_for_vol, symbol, epochs=epochs_vol, patience=patience_vol, hidden_override=hidden_vol, log_vol=True
        )
        
        if vol_model is not None:
            # N'enregistrer que si la qualité dépasse le seuil (min_r2 < 0 = désactivé)
            r2_ok = True
            if vol_metadata is not None and min_r2 > -1.0:
                try:
                    r2_ok = float(vol_metadata.get('r2_score', -1.0)) >= float(min_r2)
                except Exception:
                    r2_ok = True

            if r2_ok:
                torch.save(vol_model, volatility_path / f"{symbol}_volatility_best.pth", _use_new_zipfile_serialization=False)

                # Sauvegarder le scaler avec joblib pour compatibilité
                if vol_scaler is not None:
                    import joblib
                    joblib.dump(vol_scaler, volatility_path / f"{symbol}_scaler.pkl")

                # Sauvegarder les métadonnées (nom compatible avec ml_pipeline_manager)
                with open(volatility_path / f"{symbol}_metadata.pkl", 'wb') as f:
                    pickle.dump(vol_metadata, f)

                logger.info(f"✅ Volatility model for {symbol} saved (R²={vol_metadata.get('r2_score'):.4f})")
            else:
                logger.warning(f"⚠️ Skipped saving {symbol} volatility model (R²={vol_metadata.get('r2_score'):.4f} < threshold {min_r2})")
        else:
            logger.warning(f"❌ Failed to train volatility model for {symbol}")
    
    logger.info(f"\n🎉 Training completed!")
    logger.info(f"📍 Models location: {models_path}")
    
    return True

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Train ML models for crypto portfolio management")
    
    parser.add_argument('--symbols', nargs='+', default=None,
                       help='Specific symbols to train (e.g., --symbols BTC ETH SOL)')
    
    parser.add_argument('--skip-regime', action='store_true',
                       help='Skip regime model training')
    
    parser.add_argument('--samples', type=int, default=10000,
                       help='Number of synthetic samples to generate (default: 10000)')
    
    parser.add_argument('--only', choices=['regime', 'volatility'],
                       help='Train only specific model type')
    parser.add_argument('--real-data', action='store_true', help='Use real OHLCV data instead of synthetic')
    parser.add_argument('--days', type=int, default=2000, help='Number of historical days when using real data')
    parser.add_argument('--epochs-regime', type=int, default=200, help='Epochs for regime model')
    parser.add_argument('--patience-regime', type=int, default=15, help='Patience for regime early stopping')
    parser.add_argument('--epochs-vol', type=int, default=200, help='Epochs for volatility model')
    parser.add_argument('--patience-vol', type=int, default=15, help='Patience for volatility early stopping')
    parser.add_argument('--hidden-vol', type=int, default=0, help='Override hidden size for volatility model (0=auto)')
    parser.add_argument('--min-r2', type=float, default=0.70, help='Minimum R² to save volatility model (-1 to disable)')
    parser.add_argument('--ret30-thr', type=float, default=0.06, help='Threshold for 30d return in regime labeling (e.g., 0.04/0.05/0.06)')
    parser.add_argument('--vol-pct', type=int, default=75, help='Percentile for high volatility detection (e.g., 65/70/75)')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    logger.info("🚀 Starting ML model training...")
    
    # Determine what to train
    train_regime = not args.skip_regime
    symbols = args.symbols
    
    if args.only == 'regime':
        symbols = []
    elif args.only == 'volatility':
        train_regime = False
        
    if args.only == 'volatility' and not symbols:
        symbols = ['BTC', 'ETH', 'LINK', 'ADA', 'SOL', 'DOGE', 'AVAX']
    
    logger.info(f"Configuration: regime={train_regime}, symbols={symbols}, samples={args.samples}, real={args.real_data}, days={args.days}")
    
    save_models(
        symbols=symbols,
        train_regime=train_regime,
        samples=args.samples,
        real_data=args.real_data,
        days=args.days,
        epochs_regime=args.epochs_regime,
        patience_regime=args.patience_regime,
        epochs_vol=args.epochs_vol,
        patience_vol=args.patience_vol,
        hidden_vol=args.hidden_vol,
        min_r2=args.min_r2,
        # Passer les seuils du labeler
        ret30_thr=args.ret30_thr,
        vol_pct=args.vol_pct,
    )
    logger.info("✅ Model training complete!")
