"""
Notification Sender - Système d'envoi de notifications

Ce module gère l'envoi des notifications via différents canaux :
- Email
- Webhooks (Discord, Slack, Teams)
- Console/Logs
- WebSockets pour UI temps réel
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Protocol
from dataclasses import dataclass
import logging
import smtplib
import requests
import json
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
except ImportError:
    # Fallback pour certaines versions Python
    MimeText = None
    MimeMultipart = None

from .alert_manager import Alert, AlertLevel

logger = logging.getLogger(__name__)

class NotificationChannel(Protocol):
    """Interface pour les canaux de notification"""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Envoyer une notification"""
        ...

@dataclass
class NotificationConfig:
    """Configuration d'un canal de notification"""
    channel_type: str
    enabled: bool = True
    config: Dict[str, Any] = None
    
    # Filtres
    min_level: AlertLevel = AlertLevel.INFO
    alert_types: Optional[List[str]] = None

class ConsoleNotifier:
    """Notification via console/logs"""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Afficher dans la console"""
        
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️", 
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        
        emoji = level_emoji.get(alert.level, "📢")
        
        message = f"{emoji} [{alert.level.value.upper()}] {alert.title}"
        if alert.message:
            message += f"\n   {alert.message}"
        
        if alert.data:
            message += f"\n   Data: {json.dumps(alert.data, indent=2)}"
        
        if alert.actions:
            message += f"\n   Actions: {', '.join(alert.actions)}"
        
        # Log selon le niveau
        if alert.level == AlertLevel.CRITICAL:
            logger.critical(message)
        elif alert.level == AlertLevel.ERROR:
            logger.error(message)
        elif alert.level == AlertLevel.WARNING:
            logger.warning(message)
        else:
            logger.info(message)
        
        return True

class EmailNotifier:
    """Notification par email"""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Envoyer par email"""
        
        if not MimeText or not MimeMultipart:
            logger.warning("Email functionality not available - missing email.mime imports")
            return False
        
        try:
            smtp_host = config.get("smtp_host", "localhost")
            smtp_port = config.get("smtp_port", 587)
            username = config.get("username")
            password = config.get("password")
            from_email = config.get("from_email", "crypto-rebalancer@localhost")
            to_emails = config.get("to_emails", [])
            
            if not to_emails:
                logger.warning("No email recipients configured")
                return False
            
            # Créer le message
            msg = MimeMultipart()
            msg['From'] = from_email
            msg['To'] = ", ".join(to_emails)
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"
            
            # Corps du message
            body = self._format_email_body(alert)
            msg.attach(MimeText(body, 'html'))
            
            # Envoyer
            server = smtplib.SMTP(smtp_host, smtp_port)
            if username and password:
                server.starttls()
                server.login(username, password)
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent for alert {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _format_email_body(self, alert: Alert) -> str:
        """Formater le corps de l'email en HTML"""
        
        level_colors = {
            AlertLevel.INFO: "#17a2b8",
            AlertLevel.WARNING: "#ffc107",
            AlertLevel.ERROR: "#dc3545", 
            AlertLevel.CRITICAL: "#343a40"
        }
        
        color = level_colors.get(alert.level, "#6c757d")
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border-left: 4px solid {color}; padding: 20px; margin: 10px;">
                <h2 style="color: {color}; margin-top: 0;">
                    [{alert.level.value.upper()}] {alert.title}
                </h2>
                
                <p><strong>Message:</strong> {alert.message}</p>
                <p><strong>Source:</strong> {alert.source}</p>
                <p><strong>Heure:</strong> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                
                {self._format_data_section(alert.data) if alert.data else ""}
                {self._format_actions_section(alert.actions) if alert.actions else ""}
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _format_data_section(self, data: Dict[str, Any]) -> str:
        """Formater la section des données"""
        items = []
        for key, value in data.items():
            items.append(f"<li><strong>{key}:</strong> {value}</li>")
        
        return f"""
        <div style="margin-top: 15px;">
            <strong>Données détaillées:</strong>
            <ul>
                {"".join(items)}
            </ul>
        </div>
        """
    
    def _format_actions_section(self, actions: List[str]) -> str:
        """Formater la section des actions"""
        items = [f"<li>{action}</li>" for action in actions]
        
        return f"""
        <div style="margin-top: 15px;">
            <strong>Actions recommandées:</strong>
            <ul>
                {"".join(items)}
            </ul>
        </div>
        """

class WebhookNotifier:
    """Notification via webhooks (Discord, Slack, etc.)"""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Envoyer via webhook"""
        
        try:
            webhook_url = config.get("webhook_url")
            webhook_type = config.get("webhook_type", "generic")
            
            if not webhook_url:
                logger.warning("No webhook URL configured")
                return False
            
            # Formater selon le type de webhook
            if webhook_type == "discord":
                payload = self._format_discord_payload(alert)
            elif webhook_type == "slack":
                payload = self._format_slack_payload(alert)
            else:
                payload = self._format_generic_payload(alert)
            
            # Envoyer
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook sent for alert {alert.id}")
                return True
            else:
                logger.error(f"Webhook failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False
    
    def _format_discord_payload(self, alert: Alert) -> Dict[str, Any]:
        """Formater pour Discord"""
        
        color_map = {
            AlertLevel.INFO: 0x17a2b8,
            AlertLevel.WARNING: 0xffc107,
            AlertLevel.ERROR: 0xdc3545,
            AlertLevel.CRITICAL: 0x343a40
        }
        
        embed = {
            "title": f"[{alert.level.value.upper()}] {alert.title}",
            "description": alert.message,
            "color": color_map.get(alert.level, 0x6c757d),
            "timestamp": alert.created_at.isoformat(),
            "fields": []
        }
        
        # Ajouter les données importantes
        if alert.data:
            for key, value in list(alert.data.items())[:5]:  # Limiter à 5 champs
                embed["fields"].append({
                    "name": key.replace("_", " ").title(),
                    "value": str(value),
                    "inline": True
                })
        
        # Actions
        if alert.actions:
            actions_text = "\n".join(f"• {action}" for action in alert.actions[:3])
            embed["fields"].append({
                "name": "Actions recommandées",
                "value": actions_text,
                "inline": False
            })
        
        return {"embeds": [embed]}
    
    def _format_slack_payload(self, alert: Alert) -> Dict[str, Any]:
        """Formater pour Slack"""
        
        color_map = {
            AlertLevel.INFO: "#17a2b8",
            AlertLevel.WARNING: "#ffc107", 
            AlertLevel.ERROR: "#dc3545",
            AlertLevel.CRITICAL: "#343a40"
        }
        
        attachment = {
            "color": color_map.get(alert.level, "#6c757d"),
            "title": f"[{alert.level.value.upper()}] {alert.title}",
            "text": alert.message,
            "ts": int(alert.created_at.timestamp()),
            "fields": []
        }
        
        # Données importantes
        if alert.data:
            for key, value in list(alert.data.items())[:5]:
                attachment["fields"].append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })
        
        return {"attachments": [attachment]}
    
    def _format_generic_payload(self, alert: Alert) -> Dict[str, Any]:
        """Formater générique"""
        return {
            "alert_id": alert.id,
            "level": alert.level.value,
            "type": alert.type.value,
            "title": alert.title,
            "message": alert.message,
            "source": alert.source,
            "timestamp": alert.created_at.isoformat(),
            "data": alert.data,
            "actions": alert.actions
        }

class NotificationSender:
    """Gestionnaire principal d'envoi de notifications"""
    
    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {
            "console": ConsoleNotifier(),
            "email": EmailNotifier(),
            "webhook": WebhookNotifier()
        }
        
        self.configurations: List[NotificationConfig] = []
        
        # Configuration par défaut (console)
        self.add_config(NotificationConfig(
            channel_type="console",
            enabled=True,
            min_level=AlertLevel.INFO
        ))
    
    def add_config(self, config: NotificationConfig) -> None:
        """Ajouter une configuration de notification"""
        self.configurations.append(config)
        logger.info(f"Notification config added: {config.channel_type}")
    
    def remove_config(self, channel_type: str) -> bool:
        """Supprimer une configuration"""
        original_count = len(self.configurations)
        self.configurations = [c for c in self.configurations if c.channel_type != channel_type]
        return len(self.configurations) < original_count
    
    async def send_alert(self, alert: Alert) -> Dict[str, bool]:
        """Envoyer une alerte via tous les canaux configurés"""
        
        results = {}
        
        for config in self.configurations:
            if not config.enabled:
                continue
            
            # Vérifier les filtres
            if not self._should_send(alert, config):
                continue
            
            # Obtenir le notifier approprié
            notifier = self.channels.get(config.channel_type)
            if not notifier:
                logger.error(f"Unknown notification channel: {config.channel_type}")
                results[config.channel_type] = False
                continue
            
            # Envoyer
            try:
                success = await notifier.send(alert, config.config or {})
                results[config.channel_type] = success
                
                if success:
                    logger.debug(f"Alert {alert.id} sent via {config.channel_type}")
                else:
                    logger.warning(f"Failed to send alert {alert.id} via {config.channel_type}")
                    
            except Exception as e:
                logger.error(f"Error sending alert via {config.channel_type}: {e}")
                results[config.channel_type] = False
        
        return results
    
    def _should_send(self, alert: Alert, config: NotificationConfig) -> bool:
        """Vérifier si l'alerte doit être envoyée selon les filtres"""
        
        # Filtre par niveau minimum
        level_order = {
            AlertLevel.INFO: 0,
            AlertLevel.WARNING: 1,
            AlertLevel.ERROR: 2,
            AlertLevel.CRITICAL: 3
        }
        
        if level_order.get(alert.level, 0) < level_order.get(config.min_level, 0):
            return False
        
        # Filtre par types d'alertes
        if config.alert_types and alert.type.value not in config.alert_types:
            return False
        
        return True
    
    def get_config_status(self) -> Dict[str, Any]:
        """Obtenir le statut des configurations"""
        
        status = {
            "total_configs": len(self.configurations),
            "enabled_configs": sum(1 for c in self.configurations if c.enabled),
            "channels": {}
        }
        
        for config in self.configurations:
            channel_info = {
                "enabled": config.enabled,
                "min_level": config.min_level.value,
                "alert_types": config.alert_types
            }
            
            if config.channel_type not in status["channels"]:
                status["channels"][config.channel_type] = []
            
            status["channels"][config.channel_type].append(channel_info)
        
        return status

# Instance globale du sender
notification_sender = NotificationSender()