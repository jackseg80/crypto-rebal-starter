"""
Serveur de test temporaire pour les endpoints de risque
Lance uniquement les endpoints de risque sur le port 8001
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys
import os

# Ajouter le répertoire courant au path
sys.path.append('.')

# Import de nos endpoints de risque
from api.risk_endpoints import router as risk_router

# Créer l'application FastAPI
app = FastAPI(title="Risk Dashboard Test Server")

# CORS pour le développement
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir les fichiers statiques
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

# Inclure les routes de risque
app.include_router(risk_router)

# Route de test simple
@app.get("/")
async def root():
    return {"message": "Risk Dashboard Test Server", "status": "running"}

@app.get("/test")
async def test():
    return {"status": "OK", "endpoints": ["GET /api/risk/dashboard"]}

if __name__ == "__main__":
    import uvicorn
    print("Starting Risk Dashboard Test Server...")
    print("Dashboard available at: http://localhost:8001/static/risk-dashboard.html")
    print("API docs at: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)