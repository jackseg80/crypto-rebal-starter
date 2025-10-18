"""
Bourse Alerts Persistence Service

Stores alerts in Redis with TTL for historical tracking and acknowledgment.

Features:
- Save alerts with auto-generated IDs
- Retrieve current and historical alerts
- Mark alerts as acknowledged
- Auto-expiration with configurable TTL
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class AlertsPersistenceService:
    """
    Redis-based persistence service for alerts

    Keys structure:
    - alerts:{user_id}:current - List of current alert IDs
    - alerts:{user_id}:{alert_id} - Individual alert data
    - alerts:{user_id}:history - Sorted set of historical alerts
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        """
        Initialize persistence service

        Args:
            redis_client: Optional Redis client instance
        """
        self.redis = redis_client
        self.default_ttl = 7 * 24 * 60 * 60  # 7 days

    def _is_redis_available(self) -> bool:
        """Check if Redis is available"""
        if not self.redis:
            return False
        try:
            self.redis.ping()
            return True
        except (RedisError, Exception) as e:
            logger.warning(f"Redis not available: {e}")
            return False

    def save_alerts(
        self,
        user_id: str,
        alerts: Dict[str, List[Dict[str, Any]]],
        ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Save current alerts to Redis

        Args:
            user_id: User identifier
            alerts: Alert data with 'critical', 'warnings', 'info' lists
            ttl: Optional TTL in seconds (default 7 days)

        Returns:
            Dict with saved alert IDs and metadata
        """
        if not self._is_redis_available():
            logger.warning("Redis unavailable - alerts not persisted")
            return {'persisted': False, 'reason': 'redis_unavailable'}

        ttl = ttl or self.default_ttl
        timestamp = datetime.utcnow().isoformat() + 'Z'
        saved_ids = []

        try:
            # Generate alert IDs and add metadata
            all_alerts = alerts.get('critical', []) + alerts.get('warnings', []) + alerts.get('info', [])

            for alert in all_alerts:
                # Generate unique ID if not present
                alert_id = alert.get('id') or str(uuid.uuid4())
                alert['id'] = alert_id
                alert['user_id'] = user_id
                alert['persisted_at'] = timestamp
                alert['acknowledged'] = False
                alert['acknowledged_at'] = None

                # Save individual alert
                key = f"alerts:{user_id}:{alert_id}"
                self.redis.setex(key, ttl, json.dumps(alert))
                saved_ids.append(alert_id)

                # Add to history sorted set (score = timestamp)
                history_key = f"alerts:{user_id}:history"
                self.redis.zadd(history_key, {alert_id: datetime.utcnow().timestamp()})

            # Save current alerts list (IDs only)
            current_key = f"alerts:{user_id}:current"
            if saved_ids:
                self.redis.delete(current_key)  # Clear old current alerts
                self.redis.rpush(current_key, *saved_ids)
                self.redis.expire(current_key, ttl)

            # Save summary metadata
            summary_key = f"alerts:{user_id}:summary"
            summary_data = {
                'total': alerts.get('summary', {}).get('total', 0),
                'critical': alerts.get('summary', {}).get('critical', 0),
                'warning': alerts.get('summary', {}).get('warning', 0),
                'info': alerts.get('summary', {}).get('info', 0),
                'last_update': timestamp
            }
            self.redis.setex(summary_key, ttl, json.dumps(summary_data))

            logger.info(f"Saved {len(saved_ids)} alerts for user {user_id}")

            return {
                'persisted': True,
                'alert_ids': saved_ids,
                'count': len(saved_ids),
                'ttl': ttl,
                'timestamp': timestamp
            }

        except (RedisError, Exception) as e:
            logger.error(f"Error saving alerts to Redis: {e}")
            return {'persisted': False, 'reason': str(e)}

    def get_current_alerts(
        self,
        user_id: str,
        include_acknowledged: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieve current alerts for user

        Args:
            user_id: User identifier
            include_acknowledged: Include acknowledged alerts

        Returns:
            Dict with categorized alerts and summary
        """
        if not self._is_redis_available():
            return None

        try:
            current_key = f"alerts:{user_id}:current"
            alert_ids = self.redis.lrange(current_key, 0, -1)

            if not alert_ids:
                return None

            # Retrieve individual alerts
            alerts = []
            for alert_id in alert_ids:
                key = f"alerts:{user_id}:{alert_id.decode()}"
                alert_data = self.redis.get(key)

                if alert_data:
                    alert = json.loads(alert_data)

                    # Filter acknowledged alerts if requested
                    if not include_acknowledged and alert.get('acknowledged', False):
                        continue

                    alerts.append(alert)

            # Categorize alerts
            critical = [a for a in alerts if a.get('severity') == 'critical']
            warnings = [a for a in alerts if a.get('severity') == 'warning']
            info = [a for a in alerts if a.get('severity') == 'info']

            # Get summary
            summary_key = f"alerts:{user_id}:summary"
            summary_data = self.redis.get(summary_key)
            summary = json.loads(summary_data) if summary_data else {}

            return {
                'critical': critical,
                'warnings': warnings,
                'info': info,
                'summary': summary,
                'from_cache': True
            }

        except (RedisError, Exception) as e:
            logger.error(f"Error retrieving alerts from Redis: {e}")
            return None

    def acknowledge_alert(
        self,
        user_id: str,
        alert_id: str
    ) -> Dict[str, Any]:
        """
        Mark an alert as acknowledged

        Args:
            user_id: User identifier
            alert_id: Alert identifier

        Returns:
            Dict with acknowledgment status
        """
        if not self._is_redis_available():
            return {'acknowledged': False, 'reason': 'redis_unavailable'}

        try:
            key = f"alerts:{user_id}:{alert_id}"
            alert_data = self.redis.get(key)

            if not alert_data:
                return {'acknowledged': False, 'reason': 'alert_not_found'}

            # Update alert with acknowledgment
            alert = json.loads(alert_data)
            alert['acknowledged'] = True
            alert['acknowledged_at'] = datetime.utcnow().isoformat() + 'Z'

            # Get remaining TTL and save back
            ttl = self.redis.ttl(key)
            if ttl > 0:
                self.redis.setex(key, ttl, json.dumps(alert))
            else:
                self.redis.set(key, json.dumps(alert))

            logger.info(f"Alert {alert_id} acknowledged for user {user_id}")

            return {
                'acknowledged': True,
                'alert_id': alert_id,
                'acknowledged_at': alert['acknowledged_at']
            }

        except (RedisError, Exception) as e:
            logger.error(f"Error acknowledging alert: {e}")
            return {'acknowledged': False, 'reason': str(e)}

    def get_historical_alerts(
        self,
        user_id: str,
        limit: int = 50,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical alerts for user

        Args:
            user_id: User identifier
            limit: Maximum number of alerts to return
            days_back: Number of days to look back

        Returns:
            List of historical alerts (newest first)
        """
        if not self._is_redis_available():
            return []

        try:
            history_key = f"alerts:{user_id}:history"

            # Calculate timestamp range
            now = datetime.utcnow()
            start_time = now - timedelta(days=days_back)

            # Get alert IDs from sorted set (within time range)
            alert_ids = self.redis.zrevrangebyscore(
                history_key,
                max=now.timestamp(),
                min=start_time.timestamp(),
                start=0,
                num=limit
            )

            # Retrieve individual alerts
            alerts = []
            for alert_id in alert_ids:
                key = f"alerts:{user_id}:{alert_id.decode()}"
                alert_data = self.redis.get(key)

                if alert_data:
                    alerts.append(json.loads(alert_data))

            logger.info(f"Retrieved {len(alerts)} historical alerts for user {user_id}")
            return alerts

        except (RedisError, Exception) as e:
            logger.error(f"Error retrieving historical alerts: {e}")
            return []

    def clear_current_alerts(self, user_id: str) -> bool:
        """
        Clear current alerts for user (but keep history)

        Args:
            user_id: User identifier

        Returns:
            True if successful
        """
        if not self._is_redis_available():
            return False

        try:
            current_key = f"alerts:{user_id}:current"
            self.redis.delete(current_key)

            summary_key = f"alerts:{user_id}:summary"
            self.redis.delete(summary_key)

            logger.info(f"Cleared current alerts for user {user_id}")
            return True

        except (RedisError, Exception) as e:
            logger.error(f"Error clearing alerts: {e}")
            return False
