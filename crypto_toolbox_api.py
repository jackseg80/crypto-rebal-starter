#!/usr/bin/env python3
"""
Crypto-Toolbox API Backend
Scrape crypto-toolbox.vercel.app avec Playwright et expose les données via API
"""

import re
import time
import json
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import logging

# Configuration
app = Flask(__name__)
CORS(app)  # Permettre CORS pour les appels depuis le frontend

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL du site à scraper
CRYPTO_TOOLBOX_URL = "https://crypto-toolbox.vercel.app/signaux"

# Cache simple en mémoire (dans un vrai projet, utiliser Redis)
cache_data = {}
cache_timestamp = None
CACHE_DURATION = 300  # 5 minutes

def scrape_crypto_toolbox_data():
    """
    Scrape les données de crypto-toolbox avec Playwright
    Adapté de ton code Python existant
    """
    logger.info("🌐 Starting Crypto-Toolbox scraping...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # Charger la page
            logger.info(f"📡 Loading {CRYPTO_TOOLBOX_URL}")
            page.goto(CRYPTO_TOOLBOX_URL, timeout=15000)
            
            # Attendre que le contenu se charge
            page.wait_for_load_state("networkidle")
            time.sleep(2)  # Sécurité supplémentaire
            
            # Parser les données
            rows = page.locator("table tbody tr").all()
            logger.info(f"🔍 Found {len(rows)} table rows")
            
            indicators = []
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) < 3:
                    continue
                    
                name = cells[0].inner_text().strip()
                val_raw = cells[1].inner_text().strip()
                thr_raw = cells[2].inner_text().strip()
                
                logger.debug(f"Raw row: {name} | {val_raw} | {thr_raw}")
                
                # Gestion spéciale BMO (multiple sous-indicateurs)
                if name == "BMO (par Prof. Chaîne)":
                    vals = re.findall(r'[\d.]+', val_raw.replace(',', ''))
                    thrs = re.findall(r'(>=?\s*[\d.]+)\s*\(([^)]+)\)', thr_raw)
                    for v_str, (thr_str, label) in zip(vals, thrs):
                        val = float(v_str)
                        op, thr = parse_comparison(thr_str)
                        in_zone = (op == '>=' and val >= thr) or (op == '>' and val > thr)
                        indicators.append({
                            'name': f"{name} ({label})",
                            'value': v_str,
                            'value_numeric': val,
                            'threshold': thr_str,
                            'threshold_numeric': thr,
                            'in_critical_zone': in_zone,
                            'raw_value': val_raw,
                            'raw_threshold': thr_raw
                        })
                    continue
                
                # Traitement normal des autres indicateurs
                val_match = re.search(r'[\d.,]+', val_raw.replace(',', ''))
                if val_match:
                    val = float(val_match.group())
                    op, thr = parse_comparison(thr_raw)
                    if op is not None:
                        in_zone = {
                            '>=' : val >= thr,
                            '<=' : val <= thr,
                            '>'  : val > thr,
                            '<'  : val < thr
                        }.get(op, False)
                        
                        indicators.append({
                            'name': name,
                            'value': val_raw.replace('\n', ' '),
                            'value_numeric': val,
                            'threshold': thr_raw.replace('\n', ' '),
                            'threshold_numeric': thr,
                            'threshold_operator': op,
                            'in_critical_zone': in_zone,
                            'raw_value': val_raw,
                            'raw_threshold': thr_raw
                        })
            
            logger.info(f"✅ Successfully scraped {len(indicators)} indicators")
            browser.close()
            
            return {
                'success': True,
                'indicators': indicators,
                'total_count': len(indicators),
                'critical_count': sum(1 for ind in indicators if ind['in_critical_zone']),
                'scraped_at': datetime.now().isoformat(),
                'source': 'crypto-toolbox.vercel.app'
            }
            
        except Exception as e:
            logger.error(f"❌ Scraping error: {e}")
            browser.close()
            raise e

def parse_comparison(txt):
    """Parse les comparaisons comme >=80, <=20, etc."""
    m = re.search(r'(>=|<=|>|<)\s*([\d.,]+)', txt.replace(',', ''))
    return (m.group(1), float(m.group(2))) if m else (None, None)

@app.route('/api/crypto-toolbox', methods=['GET'])
def get_crypto_toolbox_data():
    """
    Endpoint API pour récupérer les données crypto-toolbox
    """
    global cache_data, cache_timestamp
    
    try:
        # Vérifier le cache
        current_time = time.time()
        if cache_data and cache_timestamp and (current_time - cache_timestamp) < CACHE_DURATION:
            logger.info("💾 Returning cached data")
            cache_data['cached'] = True
            cache_data['cache_age_seconds'] = int(current_time - cache_timestamp)
            return jsonify(cache_data)
        
        # Force refresh si demandé
        force_refresh = request.args.get('force', 'false').lower() == 'true'
        if force_refresh:
            logger.info("🔄 Force refresh requested")
        
        # Scraper les nouvelles données
        data = scrape_crypto_toolbox_data()
        
        # Mettre en cache
        cache_data = data
        cache_timestamp = current_time
        cache_data['cached'] = False
        
        logger.info(f"✅ API response: {data['total_count']} indicators, {data['critical_count']} critical")
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"❌ API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_time': datetime.now().isoformat()
        }), 500

@app.route('/api/crypto-toolbox/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_status': 'active' if cache_data else 'empty'
    })

@app.route('/api/crypto-toolbox/cache/clear', methods=['POST'])
def clear_cache():
    """Clear cache endpoint"""
    global cache_data, cache_timestamp
    cache_data = {}
    cache_timestamp = None
    logger.info("🧹 Cache cleared")
    return jsonify({'message': 'Cache cleared successfully'})

if __name__ == '__main__':
    logger.info("🚀 Starting Crypto-Toolbox API Backend...")
    logger.info(f"📊 Target URL: {CRYPTO_TOOLBOX_URL}")
    logger.info(f"💾 Cache duration: {CACHE_DURATION} seconds")
    
    # Démarrer le serveur Flask
    app.run(
        host='127.0.0.1',
        port=8001,
        debug=True,
        threaded=True
    )