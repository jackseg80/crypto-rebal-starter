#!/usr/bin/env bash
set -euo pipefail

# Start crypto-rebal development server with optional Crypto-Toolbox mode
#
# Usage:
#   ./start_dev.sh                    # FastAPI native (default)
#   ./start_dev.sh 0                  # Flask proxy (legacy fallback)
#   CRYPTO_TOOLBOX_NEW=0 ./start_dev.sh  # Environment variable

CRYPTO_TOOLBOX_MODE="${1:-${CRYPTO_TOOLBOX_NEW:-1}}"
PORT="${2:-8000}"
WORKERS="${3:-1}"

# Validate Playwright installation if using new mode
if [ "$CRYPTO_TOOLBOX_MODE" -eq 1 ]; then
    echo "🎭 Checking Playwright installation..."

    if ! .venv/bin/python -c "from playwright.async_api import async_playwright" 2>/dev/null; then
        echo "❌ Playwright not installed!"
        echo "   Install with: pip install playwright && playwright install chromium"
        exit 1
    fi

    echo "✅ Playwright ready"
fi

# Display configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting Crypto Rebal Development Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$CRYPTO_TOOLBOX_MODE" -eq 1 ]; then
    echo "📦 Crypto-Toolbox: FastAPI native (Playwright)"
else
    echo "📦 Crypto-Toolbox: Flask proxy (legacy)"
    echo "   ⚠️  Make sure Flask server is running on port 8001"
fi

echo "🌐 Server: http://localhost:$PORT"
echo "📚 API Docs: http://localhost:$PORT/docs"
echo "👷 Workers: $WORKERS $([ "$WORKERS" -eq 1 ] && echo '(required for Playwright)')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Set environment variable and start server
export CRYPTO_TOOLBOX_NEW="$CRYPTO_TOOLBOX_MODE"

# Note: --reload disabled for Playwright mode on Windows (asyncio subprocess incompatibility)
if [ "$CRYPTO_TOOLBOX_MODE" -eq 1 ] && [ "$(uname -s)" = "Linux" ]; then
    # Linux: reload OK with Playwright
    .venv/bin/python -m uvicorn api.main:app --reload --port "$PORT" --workers "$WORKERS"
elif [ "$CRYPTO_TOOLBOX_MODE" -eq 1 ]; then
    # Windows/Mac: no reload with Playwright
    echo "⚠️  Hot reload disabled (required for Playwright on Windows)"
    .venv/bin/python -m uvicorn api.main:app --port "$PORT" --workers "$WORKERS"
else
    # Flask mode: reload OK
    .venv/bin/python -m uvicorn api.main:app --reload --port "$PORT" --workers "$WORKERS"
fi
