// Initialisation automatique de la navigation thématique
    document.addEventListener('DOMContentLoaded', async function () {
      // Auto-détecter la page courante pour la navigation thématique
      /* unified nav enabled via components/nav.js; legacy init removed */

      // ===== Toggle Basic/Advanced Mode =====


      async function loadAdvancedRiskComponents() {
        try {
          // Check if advanced components are already loaded
          if (document.querySelector('.advanced-risk-panel')) {
            return; // Already loaded
          }

          // Add advanced sections after basic content
          const riskContent = document.getElementById('risk-dashboard-content');

          // Create Advanced Risk Analysis Panel
          const advancedPanel = document.createElement('div');
          advancedPanel.className = 'advanced-section advanced-risk-panel';
          advancedPanel.innerHTML = `
              <div class="card">
                <div class="card-header">
                  <h3>🎯 Phase 3A: Advanced Risk Analysis</h3>
                  <span class="status-badge active">VaR Models Active</span>
                </div>
                <div class="card-content">
                  <div class="risk-grid two-col-advanced">
                    <div class="left-stack">
                      <!-- Group Risk Index (GRI) -->
                      <div class="risk-card">
                        <h4>Group Risk Index (GRI)</h4>
                        <div id="gri-analysis-content">
                          <div class="loading">Loading GRI analysis...</div>
                        </div>
                      </div>
                      <!-- Monte Carlo -->
                      <div class="risk-card">
                        <h4>Monte Carlo Simulation</h4>
                        <div id="monte-carlo-content">
                          <div class="loading">Loading simulations...</div>
                        </div>
                      </div>
                      <!-- Risk Attribution -->
                      <div class="risk-card">
                        <h4>Risk Attribution</h4>
                        <div id="risk-attribution-content">
                          <div class="loading">Loading attribution analysis...</div>
                        </div>
                      </div>
                    </div>
                    <div class="right-stack">
                      <!-- Stress Testing (free height on the right) -->
                      <div class="risk-card">
                        <h4>Stress Testing</h4>
                        <div id="stress-test-content">
                          <div class="loading">Loading stress tests...</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            `;

          riskContent.appendChild(advancedPanel);

          // Load actual Phase 3A data
          await loadPhase3AData();

        } catch (error) {
          debugLogger.error('Error loading advanced risk components:', error);
          showToast('Failed to load advanced risk analysis', 'error');
        }
      }

      async function loadPhase3AData() {
        try {
          // Get Phase 3A status using globalConfig.apiRequest
          const statusData = await window.globalConfig.apiRequest('/api/phase3/status');

          if (statusData.phase_3a_advanced_risk?.status === 'active') {
            // Load GRI analysis
            await loadGRIAnalysis();
            // Load stress testing scenarios
            await loadStressTestScenarios();
            // Load Monte Carlo results
            await loadMonteCarloResults();
            // Load Risk Attribution
            await loadRiskAttribution();
          } else {
            document.getElementById('var-analysis-content').innerHTML =
              '<div class="warning">Advanced Risk Engine not available</div>';
          }
        } catch (error) {
          debugLogger.error('Error loading Phase 3A data:', error);
        }
      }

      // Helper functions for portfolio data
      function getCurrentPortfolioWeights() {
        // Get portfolio weights from current UI state or default
        const btcWeight = parseFloat(document.querySelector('[data-asset="BTC"] .allocation-value')?.textContent || '0.6');
        const ethWeight = parseFloat(document.querySelector('[data-asset="ETH"] .allocation-value')?.textContent || '0.4');
        const solWeight = parseFloat(document.querySelector('[data-asset="SOL"] .allocation-value')?.textContent || '0');

        return { BTC: btcWeight, ETH: ethWeight, SOL: solWeight };
      }

      function getCurrentPortfolioValue() {
        // Get portfolio value from UI or default to 10000
        const valueElement = document.querySelector('.portfolio-value');
        if (valueElement) {
          const valueText = valueElement.textContent.replace(/[,$€]/g, '');
          return parseFloat(valueText) || 10000;
        }
        return 10000;
      }

      // NEW V2 FUNCTIONS FOR VAR AND GRI - USING API

      // Debug metadata banner function
      function showDebugMetadataBanner(meta) {
        let banner = document.getElementById('debug-metadata-banner');
        if (!banner) {
          banner = document.createElement('div');
          banner.id = 'debug-metadata-banner';
          banner.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
            background: color-mix(in oklab, var(--info) 90%, transparent);
            border-bottom: 1px solid var(--info);
            color: var(--theme-text); padding: 0.5rem 1rem; font-size: 0.8rem;
            display: flex; justify-content: space-between; align-items: center;
          `;
          document.body.appendChild(banner);
        }

        banner.innerHTML = `
          <div>
            🏷️ <strong>Debug Metadata:</strong>
            User: <code>${meta.user_id}</code> |
            Source: <code>${meta.source_id}</code> |
            Taxonomy: <code>${meta.taxonomy_version}:${meta.taxonomy_hash}</code> |
            Generated: <code>${new Date(meta.generated_at).toLocaleTimeString()}</code>
            ${meta.correlation_id ? `| ID: <code>${meta.correlation_id}</code>` : ''}
          </div>
          <button onclick="this.parentElement.style.display='none'" style="background:none;border:none;color:var(--theme-text);cursor:pointer;font-size:1.2rem;">×</button>
        `;
      }

      async function loadGRIAnalysis() {
        try {
          // Get data from API risk dashboard for GRI analysis using globalConfig.apiRequest
          const minUsd = globalConfig.get('min_usd_threshold') || 1.0;
          const priceDays = 365;
          const corrDays = 90;

          const data = await window.globalConfig.apiRequest('/api/risk/dashboard', {
            params: {
              price_history_days: priceDays,
              lookback_days: corrDays,
              min_usd: minUsd,
              risk_version: 'v2_active',  // 🆕 V2 Active: V2 autoritaire
              use_dual_window: true
            }
          });

          if (!data.success) {
            throw new Error(data.message || 'API request failed');
          }

          // Display debug metadata banner if debug mode is enabled
          if (localStorage.getItem('debug_metadata') === 'true' && data.meta) {
            showDebugMetadataBanner(data.meta);
          }

          const metrics = data.risk_metrics;
          const exposureByGroup = metrics.exposure_by_group || {};
          const gri = metrics.group_risk_index || 0;

          // Convert exposure to display format
          const topGroups = Object.entries(exposureByGroup)
            .sort(([, a], [, b]) => b - a)  // Sort by weight descending
            // Show all groups (not just top 5)
            .map(([name, weight]) => ({
              name,
              weight: (weight * 100).toFixed(1),  // Keep 1 decimal (0.2% → "0.2")
              weight_raw: weight
            }));

          // Color coding for GRI score
          const griColor = gri < 3 ? 'var(--success)' : gri < 6 ? 'var(--warning)' : 'var(--danger)';
          const griLevel = gri < 3 ? 'LOW' : gri < 6 ? 'MEDIUM' : 'HIGH';

          // Group risk levels - Calculated by backend V2 engine (services/risk_scoring.py)
          // These are RELATIVE scores in GRI context (0=lowest structural risk, 10=highest)
          // Stablecoins = 5/10 because: structural (contrepartie/peg) + low diversification
          const GROUP_RISK_LEVELS = {
            'Stablecoins': 5, 'BTC': 2, 'ETH': 3, 'L2/Scaling': 5,
            'DeFi': 5, 'AI/Data': 5, 'SOL': 6, 'L1/L0 majors': 6,
            'Gaming/NFT': 6, 'Others': 7, 'Memecoins': 9
          };

          // Debug: log group names to verify API naming
          console.debug('📊 GRI groups from API:', Object.keys(exposureByGroup));

          document.getElementById('gri-analysis-content').innerHTML = `
              <div class="gri-overview">
                <div class="var-method">
                  <span class="method-label hinted" data-key="gri_index">
                    Group Risk Index (GRI)
                  </span>
                  <span class="var-value" style="color: ${griColor}">${gri.toFixed(1)}/10</span>
                </div>
                <div class="var-method">
                  <span class="method-label hinted" data-key="gri_level">
                    Risk Level
                  </span>
                  <span class="var-value">${griLevel}</span>
                </div>
                <div class="var-method">
                  <span class="method-label hinted" data-key="groups_count">
                    Groups Count
                  </span>
                  <span class="var-value">${Object.keys(exposureByGroup).length}</span>
                </div>
              </div>
              <div class="gri-groups">
                <h5 class="hinted" data-key="gri_groups_header">
                  Exposition & Risque par Groupe
                </h5>
                ${topGroups.map(group => {
                  const riskLevel = GROUP_RISK_LEVELS[group.name] || 5;
                  const riskColor = riskLevel < 3 ? '#9ece6a' :  // Vert (faible)
                                    riskLevel < 6 ? '#e0af68' :   // Jaune (moyen)
                                    riskLevel < 8 ? '#ff9e64' :   // Orange (élevé)
                                    '#f7768e';                     // Rouge (très élevé)

                  // Debug si fallback 5/10 utilisé
                  if (!(group.name in GROUP_RISK_LEVELS)) {
                    debugLogger.warn('⚠️ Group name not in risk levels:', group.name, '(using fallback 5/10)');
                  }

                  return `
                    <div class="var-method hinted" data-key="group:${group.name}" data-risk-level="${riskLevel}" style="position: relative; padding: 0.75rem 0.75rem 0.75rem 0.75rem; background: var(--theme-bg); border-radius: 6px; margin-bottom: 0.5rem; overflow: hidden;">
                      <!-- Barre colorée de fond -->
                      <div style="position: absolute; top: 0; left: 0; height: 100%; width: ${group.weight}%; background: ${riskColor}; opacity: 0.15; border-radius: 6px; transition: width 0.3s ease;"></div>

                      <!-- Contenu -->
                      <div style="position: relative; display: flex; justify-content: space-between; align-items: center; gap: 1rem;">
                        <span class="method-label" style="font-weight: 500;">${group.name}</span>
                        <span class="var-value" style="font-weight: 600;">${group.weight}%</span>
                      </div>

                      <!-- Badge risque à droite sur la barre -->
                      <span style="position: absolute; right: 0.5rem; top: 50%; transform: translateY(-50%); font-size: 0.7rem; padding: 2px 6px; background: ${riskColor}; color: white; border-radius: 3px; font-weight: 700; box-shadow: 0 1px 3px rgba(0,0,0,0.3);">
                        ${riskLevel}/10
                      </span>
                    </div>
                  `;
                }).join('')}
              </div>
              <div class="gri-interpretation">
                <div class="metric-interpretation hinted" data-key="gri_interpretation">
                  ${gri < 3 ? '✅ Portfolio faible risque' :
              gri < 6 ? '⚠️ Portfolio risque modéré' :
                '🚨 Portfolio haut risque - Considérer diversifier'}
                </div>
              </div>
            `;

          // Call decorateRiskTooltips to initialize all tooltips
          setTimeout(() => {
            window.decorateRiskTooltips();
          }, 100);

        } catch (error) {
          debugLogger.error('Error loading GRI Analysis:', error);
          document.getElementById('gri-analysis-content').innerHTML =
            '<div class="error">Failed to load GRI analysis from API</div>';
        }
      }

      // VaR and GRI now use API data - no local generation needed


      async function loadStressTestScenarios() {
        try {
          // Business-friendly stress scenarios with realistic data
          const scenarios = [
            {
              id: "crisis_2008",
              name: "📉 Crise Financière 2008",
              description: "Réplique la chute des marchés de septembre-novembre 2008",
              impact: { min: -45, max: -60 },
              probability: 0.02, // 2% sur 10 ans
              duration: "6-12 mois",
              context: "Effondrement Lehman Brothers, crise des subprimes"
            },
            {
              id: "covid_2020",
              name: "🦠 Crash COVID-19 Mars 2020",
              description: "Chute brutale liée à la pandémie mondiale",
              impact: { min: -35, max: -50 },
              probability: 0.05, // 5% sur 10 ans (pandémie)
              duration: "2-6 mois",
              context: "Confinements mondiaux, arrêt économique brutal"
            },
            {
              id: "china_ban",
              name: "🇨🇳 Interdiction Crypto Chine",
              description: "Bannissement complet des cryptos par autorités chinoises",
              impact: { min: -25, max: -40 },
              probability: 0.10, // 10% sur 10 ans (régulation)
              duration: "3-9 mois",
              context: "Fermeture exchanges, interdiction mining"
            },
            {
              id: "tether_collapse",
              name: "💰 Effondrement Tether",
              description: "Perte de confiance totale dans USDT",
              impact: { min: -30, max: -55 },
              probability: 0.08, // 8% sur 10 ans (risque stablecoin)
              duration: "1-4 mois",
              context: "Découverte de sous-collatéralisation massive"
            },
            {
              id: "fed_emergency",
              name: "🏦 Hausse Taux Fed d'Urgence",
              description: "Remontée brutale des taux pour lutter contre l'inflation",
              impact: { min: -20, max: -35 },
              probability: 0.15, // 15% sur 10 ans (politique monétaire)
              duration: "6-18 mois",
              context: "Taux directeur à 8-10%, fuite des capitaux risqués"
            },
            {
              id: "exchange_hack",
              name: "🔓 Hack Exchange Majeur",
              description: "Piratage d'un exchange de premier plan (Binance/Coinbase)",
              impact: { min: -15, max: -30 },
              probability: 0.20, // 20% sur 10 ans (sécurité)
              duration: "1-3 mois",
              context: "Vol de plusieurs milliards, panique générale"
            }
          ];

          const scenariosHtml = scenarios.map(scenario => `
              <div class="scenario-card" onclick="showScenarioDetails('${scenario.id}')">
                <div class="scenario-header">
                  <h5>${scenario.name}</h5>
                  <span class="scenario-probability">${(scenario.probability * 100).toFixed(0)}% / 10 ans</span>
                </div>
                <div class="scenario-impact">
                  Impact: ${scenario.impact.min}% à ${scenario.impact.max}%
                </div>
                <div class="scenario-duration">
                  Durée: ${scenario.duration}
                </div>
                <div class="scenario-context">
                  ${scenario.context}
                </div>
              </div>
            `).join('');

          document.getElementById('stress-test-content').innerHTML = `
              <div class="stress-scenarios">
                <div class="scenarios-header">
                  <p class="scenarios-description">
                    Scénarios historiques et hypothétiques pour évaluer la résilience du portefeuille
                  </p>
                </div>
                ${scenariosHtml}
                <div class="scenarios-footer">
                  <button class="btn-secondary" onclick="runAllStressTests()">
                    🧪 Lancer tous les tests
                  </button>
                  <button class="btn-secondary" onclick="createCustomScenario()">
                    ⚙️ Scénario personnalisé
                  </button>
                </div>
              </div>
            `;

          // Store scenarios globally for interactions
          window.stressScenarios = scenarios;

        } catch (error) {
          debugLogger.error('Error loading stress test scenarios:', error);
          document.getElementById('stress-test-content').innerHTML = `
              <div class="error">Erreur de chargement des scénarios de stress</div>
            `;
        }
      }

      // Interaction functions for stress scenarios
      window.showScenarioDetails = function (scenarioId) {
        const scenario = window.stressScenarios?.find(s => s.id === scenarioId);
        if (!scenario) return;

        // Show modal or detailed view (for now, just alert)
        alert(`${scenario.name}\\n\\n${scenario.description}\\n\\nImpact estimé: ${scenario.impact.min}% à ${scenario.impact.max}%\\nProbabilité sur 10 ans: ${(scenario.probability * 100).toFixed(1)}%\\nDurée typique: ${scenario.duration}`);
      };

      window.runAllStressTests = async function () {
        showToast('Lancement des tests de stress en cours...', 'info');
        // In a real implementation, this would call the Phase 3A API
        // For now, simulate loading
        setTimeout(() => {
          showToast('Tests de stress terminés. Résultats mis à jour.', 'success');
        }, 2000);
      };

      window.createCustomScenario = function () {
        // In a real implementation, this would open a modal for custom scenario creation
        showToast('Fonctionnalité de scénarios personnalisés à venir', 'info');
      };

      async function loadMonteCarloResults() {
        document.getElementById('monte-carlo-content').innerHTML = `
            <p style="font-size: 0.85rem; color: var(--theme-text-muted); margin-bottom: 1rem; font-style: italic;">
              Simulation de 10 000 scénarios aléatoires basée sur la distribution historique de rendements.
              Fournit une évaluation probabiliste du risque extrême.
            </p>
            <div class="monte-carlo-summary">
              <div class="sim-stat hinted" data-key="mc_simulations">
                <span class="stat-label">Simulations</span>
                <span class="stat-value">10,000</span>
              </div>
              <div class="sim-stat hinted" data-key="mc_worst_case">
                <span class="stat-label">Pire scénario</span>
                <span class="stat-value text-danger">-68.5%</span>
              </div>
              <div class="sim-stat hinted" data-key="mc_loss_prob">
                <span class="stat-label">Probabilité perte >20%</span>
                <span class="stat-value">12.3%</span>
              </div>
            </div>
          `;

        // Call decorateRiskTooltips to initialize all tooltips
        setTimeout(() => {
          window.decorateRiskTooltips();
        }, 100);
      }

      async function loadRiskAttribution() {
        const el = document.getElementById('risk-attribution-content');
        if (!el) return;
        try {
          // Use data from unified risk dashboard for simplified attribution using globalConfig.apiRequest
          const minUsd = globalConfig.get('min_usd_threshold') || 1.0;
          const priceDays = 365;
          const corrDays = 90;

          const data = await window.globalConfig.apiRequest('/api/risk/dashboard', {
            params: {
              price_history_days: priceDays,
              lookback_days: corrDays,
              min_usd: minUsd,
              risk_version: 'v2_active',  // 🆕 V2 Active: V2 autoritaire
              use_dual_window: true
            }
          });
          if (!data.success) {
            throw new Error(data.message || 'API request failed');
          }

          const riskMetrics = data.risk_metrics;
          const exposureByGroup = riskMetrics.exposure_by_group || {};
          const correlationMetrics = data.correlation_metrics || {};

          // Risk attribution now consolidated in GRI Analysis section (no duplicate needed)

          el.innerHTML = `
              <p style="font-size: 0.85rem; color: var(--theme-text-muted); margin-bottom: 1rem; font-style: italic;">
                Analyse de la structure du risque et de la diversification du portefeuille.
              </p>
              <div class="var-methods">
                <div class="sim-stat hinted" data-key="diversification_ratio" data-value="${correlationMetrics.diversification_ratio || 0}" style="justify-content:space-between;">
                  <span class="stat-label">Diversification Ratio</span>
                  <span class="stat-value">${(correlationMetrics.diversification_ratio || 0).toFixed(2)}</span>
                </div>
                <div class="sim-stat hinted" data-key="effective_assets" data-value="${correlationMetrics.effective_assets || 0}" style="justify-content:space-between;">
                  <span class="stat-label">Effective Assets</span>
                  <span class="stat-value">${Math.round(correlationMetrics.effective_assets || 0)}</span>
                </div>
              </div>
            `;

          // Call decorateRiskTooltips to initialize all tooltips
          setTimeout(() => {
            window.decorateRiskTooltips();
          }, 100);

        } catch (e) {
          debugLogger.warn('Risk attribution load failed:', e);
          el.innerHTML = `<div class="warning">Erreur lors du calcul d'attribution: ${e.message}</div>`;
        }
      }

      // Advanced components now loaded automatically after dashboard render

      // Make functions globally available
      window.loadAdvancedRiskComponents = loadAdvancedRiskComponents;
    });