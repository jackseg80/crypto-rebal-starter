# Dépannage

## Problèmes fréquents
- Aucune balance trouvée: vérifier `.env` (CT_API_KEY/CT_API_SECRET) et les exports CSV.
- CORS depuis pages externes: définir `CORS_ORIGINS` dans `.env`.
- OpenAPI non accessible: utiliser `/schema` (fallback) dans `api/main.py`.

## Diagnostics
- `GET /healthz`
- `GET /debug/paths`
- Logs `uvicorn` en `--reload`.

L’ancien TROUBLESHOOTING.md est déprécié au profit de cette page.

