#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safety Validator - Validation de sécurité pour l'exécution d'ordres

Ce module fournit des mécanismes de sécurité supplémentaires pour valider
que les ordres sont sûrs à exécuter et prévenir les erreurs coûteuses.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .order_manager import Order, OrderStatus

logger = logging.getLogger(__name__)

class SafetyLevel(Enum):
    """Niveaux de sécurité pour la validation"""
    STRICT = "strict"      # Mode strict - rejette tout ordre douteux
    MODERATE = "moderate"  # Mode modéré - avertissements mais passage possible
    PERMISSIVE = "permissive"  # Mode permissif - validation minimale

@dataclass 
class SafetyRule:
    """Définition d'une règle de sécurité"""
    name: str
    description: str
    check_function: callable
    severity: str  # "error", "warning", "info"
    enabled: bool = True

@dataclass
class SafetyResult:
    """Résultat d'une validation de sécurité"""
    passed: bool
    errors: List[str]
    warnings: List[str] 
    info_messages: List[str]
    total_score: float  # Score de sécurité (0-100)

class SafetyValidator:
    """Validateur de sécurité pour les ordres"""
    
    def __init__(self, safety_level: SafetyLevel = SafetyLevel.STRICT):
        self.safety_level = safety_level
        self.rules = self._initialize_safety_rules()
        self.max_daily_volume = float(os.getenv('MAX_DAILY_VOLUME_USD', '10000.0'))
        self.max_single_order = float(os.getenv('MAX_SINGLE_ORDER_USD', '1000.0'))
        self.daily_volume_used = 0.0
        
    def _initialize_safety_rules(self) -> List[SafetyRule]:
        """Initialiser les règles de sécurité"""
        return [
            SafetyRule(
                name="testnet_mode",
                description="Vérifier que nous sommes en mode testnet",
                check_function=self._check_testnet_mode,
                severity="error"
            ),
            SafetyRule(
                name="order_amount_limit",
                description="Vérifier les limites de montant par ordre",
                check_function=self._check_order_amount_limit,
                severity="error"
            ),
            SafetyRule(
                name="daily_volume_limit", 
                description="Vérifier les limites de volume quotidien",
                check_function=self._check_daily_volume_limit,
                severity="error"
            ),
            SafetyRule(
                name="symbol_whitelist",
                description="Vérifier que le symbole est autorisé",
                check_function=self._check_symbol_whitelist,
                severity="warning"
            ),
            SafetyRule(
                name="suspicious_quantity",
                description="Détecter les quantités suspectes",
                check_function=self._check_suspicious_quantity,
                severity="warning"
            ),
            SafetyRule(
                name="price_sanity",
                description="Vérifier la cohérence du prix",
                check_function=self._check_price_sanity,
                severity="warning"
            ),
            SafetyRule(
                name="production_environment",
                description="Détecter un environnement de production",
                check_function=self._check_production_environment,
                severity="error"
            )
        ]
    
    def _check_testnet_mode(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Vérifier que nous sommes en mode testnet"""
        binance_sandbox = os.getenv('BINANCE_SANDBOX', 'true').lower()
        
        if binance_sandbox != 'true':
            return False, f"DANGER: BINANCE_SANDBOX={binance_sandbox} - pas en mode testnet!"
            
        # Vérifier l'adaptateur d'exchange s'il est fourni
        if 'adapter' in context:
            adapter = context['adapter']
            if hasattr(adapter, 'config') and hasattr(adapter.config, 'sandbox'):
                if not adapter.config.sandbox:
                    return False, "DANGER: Adaptateur d'exchange pas en mode sandbox!"
        
        return True, "Mode testnet confirmé"
    
    def _check_order_amount_limit(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Vérifier les limites de montant par ordre"""
        if order.usd_amount > self.max_single_order:
            return False, f"Montant ordre ${order.usd_amount:.2f} dépasse la limite ${self.max_single_order:.2f}"
        
        if order.usd_amount <= 0:
            return False, f"Montant ordre invalide: ${order.usd_amount:.2f}"
        
        return True, f"Montant ordre ${order.usd_amount:.2f} dans les limites"
    
    def _check_daily_volume_limit(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Vérifier les limites de volume quotidien"""
        projected_daily = self.daily_volume_used + order.usd_amount
        
        if projected_daily > self.max_daily_volume:
            return False, f"Volume quotidien projeté ${projected_daily:.2f} dépasse la limite ${self.max_daily_volume:.2f}"
        
        return True, f"Volume quotidien OK: ${projected_daily:.2f}/${self.max_daily_volume:.2f}"
    
    def _check_symbol_whitelist(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Vérifier que le symbole est dans la whitelist"""
        # Symboles autorisés pour les tests
        allowed_symbols = {
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'DOT/USDT',
            'BTC', 'ETH', 'BNB', 'ADA', 'DOT'  # Formats alternatifs
        }
        
        symbol_variants = {order.symbol, order.symbol.replace('/', ''), 
                          order.symbol.replace('USDT', '').replace('/', '')}
        
        if not any(variant in allowed_symbols for variant in symbol_variants):
            return False, f"Symbole {order.symbol} pas dans la whitelist de test"
        
        return True, f"Symbole {order.symbol} autorisé"
    
    def _check_suspicious_quantity(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Détecter les quantités suspectes"""
        # Quantités extrêmes qui pourraient indiquer une erreur
        if order.quantity > 1000:  # Plus de 1000 unités
            return False, f"Quantité suspecte: {order.quantity} (très élevée)"
        
        if order.quantity > 0 and order.quantity < 0.000001:  # Moins de 1 satoshi
            return False, f"Quantité suspecte: {order.quantity} (très faible)"
        
        return True, f"Quantité {order.quantity} semble normale"
    
    def _check_price_sanity(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Vérifier la cohérence du prix"""
        if order.quantity > 0 and order.usd_amount > 0:
            implied_price = order.usd_amount / order.quantity
            
            # Prix Bitcoin suspects (en dehors de $10k-$200k)
            if 'BTC' in order.symbol.upper():
                if implied_price < 10000 or implied_price > 200000:
                    return False, f"Prix BTC suspect: ${implied_price:.2f}"
            
            # Prix Ethereum suspects (en dehors de $100-$10k)
            elif 'ETH' in order.symbol.upper():
                if implied_price < 100 or implied_price > 10000:
                    return False, f"Prix ETH suspect: ${implied_price:.2f}"
        
        return True, "Prix cohérent"
    
    def _check_production_environment(self, order: Order, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Détecter un environnement de production"""
        # Indicateurs d'environnement de production
        prod_indicators = [
            os.getenv('NODE_ENV') == 'production',
            os.getenv('ENVIRONMENT') == 'production', 
            os.getenv('DEPLOYMENT_ENV') == 'production',
            os.getenv('BINANCE_SANDBOX', 'true').lower() == 'false'
        ]
        
        if any(prod_indicators):
            return False, "DANGER: Environnement de production détecté!"
        
        return True, "Environnement de test confirmé"
    
    def validate_order(self, order: Order, context: Optional[Dict[str, Any]] = None) -> SafetyResult:
        """Valider un ordre selon les règles de sécurité"""
        if context is None:
            context = {}
        
        errors = []
        warnings = []
        info_messages = []
        score = 100.0
        
        logger.info(f"Validation sécurité ordre {order.id}: {order.action} {order.quantity} {order.symbol} (~${order.usd_amount})")
        
        for rule in self.rules:
            if not rule.enabled:
                continue
                
            try:
                passed, message = rule.check_function(order, context)
                
                if not passed:
                    if rule.severity == "error":
                        errors.append(f"{rule.name}: {message}")
                        score -= 30  # Pénalité lourde pour les erreurs
                    elif rule.severity == "warning":
                        warnings.append(f"{rule.name}: {message}")
                        score -= 10  # Pénalité modérée pour les avertissements
                else:
                    info_messages.append(f"{rule.name}: {message}")
                    
            except Exception as e:
                error_msg = f"Erreur validation règle {rule.name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                score -= 20
        
        # Déterminer le résultat global
        passed = len(errors) == 0
        
        # En mode strict, les warnings sont des erreurs
        if self.safety_level == SafetyLevel.STRICT and len(warnings) > 0:
            passed = False
        
        result = SafetyResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            info_messages=info_messages,
            total_score=max(0.0, score)
        )
        
        # Log du résultat
        if passed:
            logger.info(f"✓ Ordre {order.id} validé avec succès (score: {result.total_score:.1f}/100)")
        else:
            logger.error(f"✗ Ordre {order.id} rejeté (score: {result.total_score:.1f}/100)")
            for error in errors:
                logger.error(f"  - {error}")
        
        return result
    
    def validate_orders(self, orders: List[Order], context: Optional[Dict[str, Any]] = None) -> Dict[str, SafetyResult]:
        """Valider une liste d'ordres"""
        results = {}
        total_volume = sum(order.usd_amount for order in orders)
        
        logger.info(f"Validation de {len(orders)} ordres (volume total: ${total_volume:.2f})")
        
        # Vérification du volume total
        if total_volume > self.max_daily_volume:
            logger.error(f"Volume total ${total_volume:.2f} dépasse la limite quotidienne ${self.max_daily_volume:.2f}")
        
        for order in orders:
            results[order.id] = self.validate_order(order, context)
            
            # Accumuler le volume si l'ordre est valide
            if results[order.id].passed:
                self.daily_volume_used += order.usd_amount
        
        return results
    
    def get_safety_summary(self, results: Dict[str, SafetyResult]) -> Dict[str, Any]:
        """Obtenir un résumé de la validation de sécurité"""
        total_orders = len(results)
        passed_orders = sum(1 for r in results.values() if r.passed)
        total_errors = sum(len(r.errors) for r in results.values())
        total_warnings = sum(len(r.warnings) for r in results.values())
        avg_score = sum(r.total_score for r in results.values()) / total_orders if total_orders > 0 else 0
        
        return {
            "total_orders": total_orders,
            "passed_orders": passed_orders,
            "failed_orders": total_orders - passed_orders,
            "success_rate": (passed_orders / total_orders * 100) if total_orders > 0 else 0,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "average_score": avg_score,
            "daily_volume_used": self.daily_volume_used,
            "daily_volume_limit": self.max_daily_volume,
            "is_safe": total_errors == 0 and avg_score >= 80.0
        }

# Instance globale pour une utilisation facile
safety_validator = SafetyValidator()