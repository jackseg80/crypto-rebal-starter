#!/usr/bin/env bash
set -euo pipefail

# Start crypto-rebal development server with optional features
#
# Usage:
#   ./start_dev.sh                           # Default: FastAPI native, no scheduler, port 8080
#   ./start_dev.sh -s                        # Enable scheduler
#   ./start_dev.sh -r                        # Enable hot reload (only with Flask mode)
#   ./start_dev.sh -p 8001                   # Custom port
#   ./start_dev.sh -s -p 8081                # Scheduler on custom port
#   ./start_dev.sh -c 0 -r                   # Flask proxy with hot reload
#   ./start_dev.sh -h                        # Show help
#
# Options:
#   -c MODE    Crypto-Toolbox mode: 0=Flask proxy (legacy), 1=FastAPI native (default: 1)
#   -s         Enable task scheduler (P&L snapshots, OHLCV updates, warmers)
#   -r         Enable hot reload (auto-disabled if Scheduler or Playwright enabled)
#   -p PORT    Server port (default: 8080)
#   -h         Show this help message

# Default values
CRYPTO_TOOLBOX_MODE="${CRYPTO_TOOLBOX_NEW:-1}"
ENABLE_SCHEDULER=0
ENABLE_RELOAD=0
PORT=8080
WORKERS=1

# Parse command line arguments
show_help() {
    head -n 20 "$0" | grep "^#" | sed 's/^# \?//'
    exit 0
}

while getopts "c:srp:h" opt; do
    case $opt in
        c) CRYPTO_TOOLBOX_MODE="$OPTARG" ;;
        s) ENABLE_SCHEDULER=1 ;;
        r) ENABLE_RELOAD=1 ;;
        p) PORT="$OPTARG" ;;
        h) show_help ;;
        \?) echo "Invalid option: -$OPTARG. Use -h for help." >&2; exit 1 ;;
    esac
done

# Check virtual environment exists
if [ ! -f ".venv/bin/python" ]; then
    echo ""
    echo "❌ Virtual environment not found!"
    echo "   Please create it first:"
    echo "   1. python -m venv .venv"
    echo "   2. source .venv/bin/activate"
    echo "   3. pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Check and start Redis
echo "🔍 Checking Redis..."

# Try localhost first
REDIS_RUNNING=0
if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
    echo "✅ Redis is running on localhost"
    REDIS_RUNNING=1
else
    # Try to start Redis service (systemd)
    if command -v systemctl &> /dev/null; then
        echo "   Starting Redis via systemd..."
        if sudo systemctl start redis-server 2>/dev/null || sudo systemctl start redis 2>/dev/null; then
            sleep 1
            if redis-cli ping &> /dev/null; then
                echo "✅ Redis started successfully"
                REDIS_RUNNING=1
            fi
        fi
    # Fallback to init.d
    elif command -v service &> /dev/null; then
        echo "   Starting Redis via service..."
        if sudo service redis-server start 2>/dev/null; then
            sleep 1
            if redis-cli ping &> /dev/null; then
                echo "✅ Redis started successfully"
                REDIS_RUNNING=1
            fi
        fi
    fi
fi

if [ $REDIS_RUNNING -eq 0 ]; then
    echo "⚠️  Redis not accessible - server will run in degraded mode"
fi

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

# Determine reload mode (auto-disable if Scheduler or Playwright enabled)
USE_RELOAD=0
if [ $ENABLE_RELOAD -eq 1 ] && [ $ENABLE_SCHEDULER -eq 0 ] && [ "$CRYPTO_TOOLBOX_MODE" -ne 1 ]; then
    USE_RELOAD=1
fi

# Display configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting Crypto Rebal Development Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Crypto-Toolbox mode
if [ "$CRYPTO_TOOLBOX_MODE" -eq 1 ]; then
    echo "📦 Crypto-Toolbox: FastAPI native (Playwright)"
else
    echo "📦 Crypto-Toolbox: Flask proxy (legacy)"
    echo "   ⚠️  Make sure Flask server is running on port 8001"
fi

# Scheduler mode
if [ $ENABLE_SCHEDULER -eq 1 ]; then
    echo "⏰ Task Scheduler: ENABLED"
    echo "   • P&L snapshots (intraday 15min, EOD 23:59)"
    echo "   • OHLCV updates (daily 03:10, hourly :05)"
    echo "   • Staleness monitor (hourly :15)"
    echo "   • API warmers (every 10min)"
    echo "   • Crypto-Toolbox indicators (2x daily: 08:00, 20:00)"
else
    echo "⏰ Task Scheduler: DISABLED"
    echo "   Run manual scripts for P&L/OHLCV updates"
fi

# Reload mode
if [ $USE_RELOAD -eq 1 ]; then
    echo "🔄 Hot Reload: ENABLED"
else
    echo "🔄 Hot Reload: DISABLED"
    if [ $ENABLE_SCHEDULER -eq 1 ]; then
        echo "   (auto-disabled: prevents double execution with scheduler)"
    elif [ "$CRYPTO_TOOLBOX_MODE" -eq 1 ]; then
        echo "   (auto-disabled: required for Playwright compatibility)"
    fi
fi

echo ""
echo "🌐 Server: http://localhost:$PORT"
echo "📚 API Docs: http://localhost:$PORT/docs"
echo "🩺 Scheduler Health: http://localhost:$PORT/api/scheduler/health"
echo "👷 Workers: 1 (single worker mode for Playwright compatibility)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Set environment variables
export CRYPTO_TOOLBOX_NEW="$CRYPTO_TOOLBOX_MODE"

if [ $ENABLE_SCHEDULER -eq 1 ]; then
    export RUN_SCHEDULER="1"
    echo "✅ Environment: RUN_SCHEDULER=1"
else
    export RUN_SCHEDULER="0"
fi

# Check if port is available
echo "🔌 Checking if port $PORT is available..."
sleep 0.2 # Brief pause to allow ports to be released

PORT_IN_USE=0
if command -v lsof &> /dev/null; then
    if lsof -i ":$PORT" -sTCP:LISTEN &> /dev/null; then
        PORT_IN_USE=1
    fi
elif command -v netstat &> /dev/null; then
    if netstat -tuln | grep -q ":$PORT "; then
        PORT_IN_USE=1
    fi
elif command -v ss &> /dev/null; then
    if ss -tuln | grep -q ":$PORT "; then
        PORT_IN_USE=1
    fi
fi

if [ $PORT_IN_USE -eq 1 ]; then
    echo ""
    echo "❌ Port $PORT is already in use by another process!"
    echo "   Please stop the existing process or use a different port."
    if command -v lsof &> /dev/null; then
        echo "   To find the process, run: lsof -i :$PORT"
    fi
    echo "   Example: ./start_dev.sh -p 8001"
    echo ""
    exit 1
fi

echo "🚀 Starting Uvicorn..."
echo ""

# Start server
if [ $USE_RELOAD -eq 1 ]; then
    # For --reload, uvicorn uses single worker (--workers flag is incompatible)
    .venv/bin/python -m uvicorn api.main:app --reload --port "$PORT"
else
    # Without --reload, single worker mode for Playwright compatibility
    .venv/bin/python -m uvicorn api.main:app --port "$PORT"
fi
