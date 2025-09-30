#!/usr/bin/env python3
"""
Simple starter for crypto-rebal-starter without heavy dependencies
Just serves the static files and basic endpoints for HTTP testing
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Crypto Rebalancer (Simple)")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")

@app.get("/")
async def root():
    return {"message": "Crypto Rebalancer (Simple Mode)", "status": "OK"}

@app.get("/docs")
async def docs():
    return {"message": "Simple mode - no API docs available"}

@app.get("/balances/current")
async def balances():
    return {
        "balances": [
            {"symbol": "BTC", "amount": 0.5, "value_usd": 25000},
            {"symbol": "ETH", "amount": 10, "value_usd": 15000}
        ],
        "total_usd": 40000,
        "source": "stub"
    }

if __name__ == "__main__":
    print("Starting Crypto Rebalancer in Simple Mode...")
    print("Dashboard: http://localhost:8000/static/dashboard.html")
    print("Analytics: http://localhost:8000/static/analytics-unified.html")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)