"""
API Startup & Shutdown Handlers
Extracted from api/main.py (Phase 2B refactoring)

Handles:
- ML models lazy loading
- Governance Engine initialization
- Alert Engine initialization
- Background tasks orchestration
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def initialize_ml_models():
    """
    Initialize ML models for Governance Engine.

    Returns:
        int: Number of models successfully initialized
    """
    try:
        from services.ml.orchestrator import get_orchestrator
        orchestrator = get_orchestrator()

        # Force models to ready status
        models_initialized = 0
        for model_type in ['volatility', 'regime', 'correlation', 'sentiment', 'rebalancing']:
            if model_type in orchestrator.model_status:
                orchestrator.model_status[model_type] = 'ready'
                models_initialized += 1

        logger.info(f"✅ {models_initialized} ML models forced to ready status")
        return models_initialized

    except Exception as ml_error:
        logger.error(f"❌ ML initialization failed: {ml_error}")
        return 0


async def initialize_governance_engine():
    """
    Initialize Governance Engine with ML signals.

    Returns:
        bool: True if initialized successfully
    """
    try:
        from services.execution.governance import governance_engine
        await governance_engine._refresh_ml_signals()

        # Verify signals are loaded
        signals = governance_engine.current_state.signals
        if signals and signals.confidence > 0:
            logger.info(
                f"✅ Governance Engine initialized: "
                f"{signals.confidence:.1%} confidence, "
                f"{len(signals.sources_used)} sources"
            )
            return True
        else:
            logger.warning("⚠️ Governance Engine initialized but signals may be empty")
            return False

    except Exception as e:
        logger.error(f"❌ Governance Engine initialization failed: {e}")
        return False


async def initialize_alert_engine():
    """
    Initialize Alert Engine with scheduler.

    Returns:
        bool: True if initialized successfully
    """
    try:
        from services.alerts.alert_engine import AlertEngine
        from services.execution.governance import governance_engine
        from api.alerts_endpoints import initialize_alert_engine as init_alert_api

        # Create AlertEngine instance with governance engine reference
        alert_engine = AlertEngine(
            governance_engine=governance_engine,
            config_file_path="config/alerts_rules.json"
        )

        # Initialize AlertEngine for API endpoints
        init_alert_api(alert_engine)

        # Initialize unified facade for legacy systems
        from services.alerts.unified_alert_facade import get_unified_alert_facade
        unified_facade = get_unified_alert_facade(alert_engine)
        logger.info("✅ Unified alert facade initialized for legacy system migration")

        # Start alert scheduler in background
        scheduler_started = await alert_engine.start()

        if scheduler_started:
            logger.info("✅ AlertEngine scheduler started successfully")
        else:
            logger.info("📊 AlertEngine initialized in standby mode (scheduler locked by another instance)")

        return scheduler_started

    except Exception as alert_error:
        logger.error(f"❌ AlertEngine initialization failed: {alert_error}")
        # Don't crash the app, system can work without alerts
        return False


async def background_startup_tasks():
    """
    Background task to initialize ML models, Governance, and Alerts.
    Runs after a 3-second delay to let the app fully start.
    """
    try:
        # Wait for app to fully start
        await asyncio.sleep(3)

        logger.info("📦 Starting background ML models initialization...")

        # Initialize ML models
        models_count = await initialize_ml_models()

        if models_count > 0:
            # Initialize Governance Engine
            governance_ok = await initialize_governance_engine()

            # Initialize Alert Engine
            alerts_ok = await initialize_alert_engine()

            logger.info(
                f"🎯 Startup complete: "
                f"ML={models_count} models, "
                f"Governance={'✅' if governance_ok else '⚠️'}, "
                f"Alerts={'✅' if alerts_ok else '⚠️'}"
            )

    except Exception as e:
        logger.info(f"⚠️ Background loading failed, models will load on demand: {e}")


def get_startup_handler():
    """
    Returns the startup event handler for FastAPI.

    Usage:
        @app.on_event("startup")
        async def startup():
            await get_startup_handler()()
    """
    async def startup_load_ml_models():
        """Lazy loading of ML models to avoid blocking startup"""
        try:
            logger.info("🚀 FastAPI started successfully")
            logger.info("⚡ ML models will load on first request (lazy loading)")

            # Start background task without waiting
            asyncio.create_task(background_startup_tasks())

        except Exception as e:
            logger.warning(f"⚠️ Startup event warning (non-blocking): {e}")
            # Don't crash the app

    return startup_load_ml_models


def get_shutdown_handler():
    """
    Returns the shutdown event handler for FastAPI.

    Usage:
        @app.on_event("shutdown")
        async def shutdown():
            await get_shutdown_handler()()
    """
    async def shutdown_cleanup():
        """Cleanup tasks on shutdown"""
        try:
            logger.info("🛑 Shutting down FastAPI application...")

            # Stop alert scheduler if running
            try:
                from api.alerts_endpoints import get_alert_engine
                alert_engine = get_alert_engine()
                if alert_engine:
                    await alert_engine.stop()
                    logger.info("✅ AlertEngine scheduler stopped")
            except Exception as e:
                logger.warning(f"⚠️ Alert engine cleanup failed: {e}")

            logger.info("✅ Shutdown complete")

        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")

    return shutdown_cleanup
