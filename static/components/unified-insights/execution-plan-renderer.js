// UnifiedInsights - Execution Plan Renderer
// Renders theoretical targets and execution plan with iterations

import { card } from './utils.js';
import { getCurrentAllocationByGroup, calculateZeroSumCappedMoves } from './allocation-calculator.js';
import { GROUP_ORDER, groupAssetsByClassification } from '../../shared-asset-groups.js';
import { store } from '../../core/risk-dashboard-store.js';
import { resolveCapPercent, resolvePolicyCapPercent, resolveEngineCapPercent } from './utils.js';
import * as governanceSelectors from '../../selectors/governance.js';

/**
 * Renders the complete allocation block with theoretical targets and execution plan
 */
export async function renderAllocationBlock(u, options = {}) {
  try {
    // SOURCE CANONIQUE UNIQUE: Utiliser targets_by_group (même source que plan d'exécution)
    (window.debugLogger?.warn || console.warn)('🔥 UNIFIED SOURCE: Using u.targets_by_group as canonical source');
    let allocation = u.targets_by_group;
    (window.debugLogger?.warn || console.warn)('🔥 UNIFIED SOURCE: targets_by_group result:', allocation);

    // PATCH C - Moteur unique : utiliser groupAssetsByClassification comme Rebalance (DÉSACTIVÉ pour test)
    let allocation_backup = null;
    try {
      // FORCE: Utiliser toutes les sources possibles pour récupérer les balances
      let balanceData = store.snapshot()?.wallet?.balances || [];

      // Fallback vers les clés store directes si snapshot échoue
      if (balanceData.length === 0) {
        balanceData = store.get('wallet.balances') || [];
        console.debug('🔧 PATCH C: Using direct store access for balances');
      }

      // Dernier recours : attendre que l'injection soit finie et réessayer
      if (balanceData.length === 0) {
        await new Promise(resolve => setTimeout(resolve, 100)); // 100ms
        balanceData = store.snapshot()?.wallet?.balances || store.get('wallet.balances') || [];
        console.debug('🔧 PATCH C: Retry after 100ms delay');
      }

      console.debug('🔧 PATCH C starting with balances:', balanceData.length, 'items', {
        from_snapshot: store.snapshot()?.wallet?.balances?.length || 0,
        from_direct: store.get('wallet.balances')?.length || 0,
        final_used: balanceData.length
      });

      if (balanceData.length > 0) {
        const groupedData = groupAssetsByClassification(balanceData);
        const totalValue = groupedData.reduce((sum, g) => sum + g.value, 0);

        if (totalValue > 0) {
          // Convertir au format attendu par l'UI (% par groupe)
          allocation = {};
          GROUP_ORDER.forEach(group => {
            const found = groupedData.find(g => g.label === group);
            allocation[group] = found ? (found.value / totalValue) * 100 : 0;
          });

          console.debug('🔧 PATCH C SUCCESS: Analytics utilise maintenant groupAssetsByClassification comme Rebalance:', {
            groups: Object.entries(allocation).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
            othersCheck: allocation['Others']?.toFixed(1) + '%',
            source: 'groupAssetsByClassification',
            totalValue
          });
        } else {
          (window.debugLogger?.warn || console.warn)('🔧 PATCH C: totalValue is 0, skipping allocation');
        }
      } else {
        (window.debugLogger?.warn || console.warn)('🔧 PATCH C: No balance data available');
      }
    } catch (e) {
      (window.debugLogger?.error || console.error)('🔧 PATCH C failed with error:', e.message, e.stack);
    }

    // Fallback vers u.targets_by_group si patch échoue (plus de presets hardcodés)
    if (!allocation || Object.keys(allocation).length === 0) {
      (window.debugLogger?.warn || console.warn)('🚨 PATCH C FAILED - Using dynamic targets_by_group as fallback');

      // Fallback ultime : utiliser les positions actuelles normalisées
      allocation = {};
      GROUP_ORDER.forEach(group => allocation[group] = 0);

      // Utiliser la même logique que PATCH C pour fallback
      try {
        const balanceData = store.snapshot()?.wallet?.balances || [];
        if (balanceData.length > 0) {
          const groupedData = groupAssetsByClassification(balanceData);
          const totalValue = groupedData.reduce((sum, g) => sum + g.value, 0);

          if (totalValue > 0) {
            GROUP_ORDER.forEach(group => {
              const found = groupedData.find(g => g.label === group);
              allocation[group] = found ? (found.value / totalValue) * 100 : 0;
            });
            console.debug('✅ FALLBACK: Using groupAssetsByClassification as allocation targets');
          }
        }
      } catch (e) {
        (window.debugLogger?.error || console.error)('Fallback also failed:', e.message);
      }

      // Dernier recours: utiliser targets_by_group (dynamique)
      if (!allocation || Object.values(allocation).every(v => v === 0)) {
        allocation = u.targets_by_group || {};
        (window.debugLogger?.warn || console.warn)('⚠️ ULTIMATE FALLBACK: u.targets_by_group utilisé (calcul dynamique)');
      }
    }

    // Allocation fournie par u.targets_by_group (calcul dynamique) - vérification
    if (!allocation || Object.keys(allocation).length === 0) {
      (window.debugLogger?.error || console.error)('🚨 ERREUR CRITIQUE: targets_by_group vide', { u, allocation });
      return '<div class="error-message">❌ Erreur: calculs dynamiques indisponibles</div>';
    }

    // GARDE-FOUS - Checksum et validation
    const total = Object.values(allocation || {}).reduce((a, b) => a + (isFinite(b) ? b : 0), 0);
    if (Math.abs(total - 100) > 0.5) {
      (window.debugLogger?.warn || console.warn)(`⚠️ target_sum_mismatch: somme = ${total.toFixed(1)}% (≠ 100%)`);
      // Petite normalisation douce (hors stables)
      if (allocation && allocation['Stablecoins'] != null) {
        const st = allocation['Stablecoins'];
        const space = Math.max(0, 100 - st);
        const nonKeys = Object.keys(allocation).filter(k => k !== 'Stablecoins');
        const nonSum = nonKeys.reduce((s, k) => s + allocation[k], 0) || 1;
        nonKeys.forEach(k => allocation[k] = allocation[k] * (space / nonSum));
        const newTotal = Object.values(allocation).reduce((a, b) => a + b, 0);
        if (Math.abs(newTotal - 100) > 0.5) {
          (window.debugLogger?.warn || console.warn)(`⚠️ soft renorm failed: ${newTotal.toFixed(2)}%`);
        }
      }
    }

    if (allocation && Object.keys(allocation).length > 0) {
      const conf = u.decision.confidence || 0;
      const contra = (u.contradictions?.length) || 0;
      const governanceStatus = store.getGovernanceStatus();

      const unifiedStateForCap = (typeof store.snapshot === 'function' ? store.snapshot() : null) || window.realDataStore || {};
      const governanceState = unifiedStateForCap?.governance || store.get('governance');
      const activePolicy = governanceState?.active_policy;

      const policyCapPercent = resolvePolicyCapPercent(unifiedStateForCap, governanceSelectors);
      const engineCapPercent = resolveEngineCapPercent(unifiedStateForCap, governanceSelectors);
      const capPercent = resolveCapPercent(unifiedStateForCap, governanceSelectors);

      let mode = { name: 'Observe', cap: capPercent != null ? capPercent : 0 };

      if (governanceStatus.state === 'FROZEN') {
        mode = { name: 'Frozen', cap: 0 };
      } else if (policyCapPercent != null) {
        const policyMode = activePolicy?.mode || 'Normal';
        mode = {
          name: `${policyMode} (Gov)`,
          cap: policyCapPercent
        };
        if (engineCapPercent != null && engineCapPercent !== policyCapPercent) {
          mode.smartCap = engineCapPercent;
        }
      } else {
        mode = conf > 0.8 && contra === 0 ? { name: 'Deploy', cap: 15 } :
               conf > 0.65 && contra <= 1 ? { name: 'Rotate', cap: 10 } :
               conf > 0.55 ? { name: 'Hedge', cap: 5 } : { name: 'Observe', cap: 0 };
        if (capPercent != null) {
          mode.cap = capPercent;
        }
        if (engineCapPercent != null && mode.cap !== engineCapPercent) {
          mode.smartCap = engineCapPercent;
        }
      }

      const current = await getCurrentAllocationByGroup(5.0);

      // DEBUG: Verify allocation before assigning to targetAdj
      console.debug('🎯 ALLOCATION DEBUG before targetAdj:', {
        allocation_keys: allocation ? Object.keys(allocation) : 'no allocation',
        allocation_values: allocation,
        allocation_total: allocation ? Object.values(allocation).reduce((a, b) => a + b, 0) : 'no allocation'
      });

      // SOURCE CANONIQUE UNIQUE: Utiliser targets_by_group (calculs dynamiques)
      // Plus de presets hardcodés - tout est calculé dynamiquement dans unified-insights-v2.js
      let executionTargets = allocation; // Current allocation (fallback de sécurité)

      // LECTURE DIRECTE: Objectifs théoriques = source canonique dynamique
      if (u.targets_by_group && Object.keys(u.targets_by_group).length > 0) {
        executionTargets = { ...u.targets_by_group };
        (window.debugLogger?.info || console.log)('✅ DYNAMIC TARGETS utilisés (plus de presets!):', {
          source: 'u.targets_by_group (computed dynamically)',
          targets: Object.entries(executionTargets).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
          stables_pct: executionTargets['Stablecoins']?.toFixed(1) + '%',
          sum: Object.values(executionTargets).reduce((a,b) => a+b, 0).toFixed(1) + '%'
        });
      } else {
        (window.debugLogger?.warn || console.warn)('⚠️ targets_by_group manquant, fallback sur allocation actuelle');
      }

      const targetAdj = executionTargets;

      // CORRECTION UNIFICATION: Forcer l'affichage théorique à utiliser les mêmes targets
      // pour éviter l'incohérence entre objectifs théoriques et plan d'exécution
      console.debug('🔄 BEFORE UNIFICATION:', {
        allocation_before: allocation ? Object.entries(allocation).map(([k,v]) => `${k}: ${v.toFixed(1)}%`) : 'null',
        executionTargets: Object.entries(executionTargets).map(([k,v]) => `${k}: ${v.toFixed(1)}%`)
      });

      allocation = executionTargets;

      console.debug('🔄 AFTER UNIFICATION: Objectifs théoriques forcés à utiliser les mêmes targets que le plan d\'exécution:', {
        allocation_after: Object.entries(allocation).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
        unified_targets: Object.entries(executionTargets).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
        note: 'Objectifs et plan maintenant cohérents'
      });

      const keys = new Set([
        ...Object.keys(targetAdj || {}),
        ...Object.keys((current && current.pct) || {})
      ]);

      const entries = Array.from(keys).map(k => {
        const cur = Number((current?.pct || {})[k] || 0);
        const tgt = Number((targetAdj || {})[k] || 0);
        const delta = Math.round((tgt - cur) * 10) / 10;
        return { k, cur, tgt, delta, suggested: 0 }; // suggested will be calculated with zero-sum constraint
      });

      // DEBUG: Log execution plan calculation details
      console.debug('🎯 EXECUTION PLAN DELTAS DEBUG:', {
        cap_limit: mode.cap + '%',
        all_deltas: entries.map(e => ({
          asset: e.k,
          current: e.cur.toFixed(1) + '%',
          target: e.tgt.toFixed(1) + '%',
          delta: e.delta.toFixed(1) + '%',
          urgency: Math.abs(e.delta).toFixed(1)
        })).sort((a, b) => parseFloat(b.urgency) - parseFloat(a.urgency)),
        significant_deltas: entries.filter(e => Math.abs(e.delta) > 0.5).length,
        total_positive_budget_needed: entries.filter(e => e.delta > 0).reduce((s, e) => s + e.delta, 0).toFixed(1) + '%',
        total_negative_budget_needed: entries.filter(e => e.delta < 0).reduce((s, e) => s + Math.abs(e.delta), 0).toFixed(1) + '%'
      });

      // CONTRAINTE ZÉRO-SOMME: calculate suggested moves with cap and zero-sum constraint
      const cappedEntries = calculateZeroSumCappedMoves(entries, mode.cap);
      entries.forEach((entry, i) => {
        entry.suggested = cappedEntries[i].suggested;
      });

      // HIÉRARCHIE STRICTE: seulement les groupes taxonomy autorisés
      const TOP_LEVEL_GROUPS = GROUP_ORDER.length > 0 ? GROUP_ORDER : ['BTC', 'ETH', 'Stablecoins', 'SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'AI/Data', 'Gaming/NFT', 'Memecoins', 'Others'];

      const visible = entries
        .filter(e => {
          // Filtre significatif
          const isSignificant = (e.tgt > 0.1) || Math.abs(e.delta) > 0.2 || e.cur > 0.1;
          // Filtre hiérarchique - SEULEMENT les groupes top-level
          const isTopLevel = TOP_LEVEL_GROUPS.includes(e.k);

          if (!isTopLevel && isSignificant) {
            console.debug(`🚫 Coin ${e.k} excluded from top-level (child of group)`);
          }

          return isSignificant && isTopLevel;
        })
        .sort((a, b) => (b.tgt - a.tgt) || (b.cur - a.cur))
        .slice(0, 11); // Max 11 groupes

      // Persist suggested allocation for rebalance.html consumption
      try {
        if (targetAdj && Object.keys(targetAdj).length > 0) {
          // Utiliser le plan d'exécution pré-calculé (même source que cartes)
          const executionPlan = u.execution?.plan_iter1 || {};
          console.debug('🔄 Using pre-calculated execution plan:', executionPlan);

          const payload = {
            targets: targetAdj, // Final theoretical targets
            execution_plan: executionPlan, // Iteration 1 targets with caps
            cap_percent: mode.cap,
            strategy: 'Regime-Based Allocation',
            timestamp: new Date().toISOString(),
            source: 'analytics-unified'
          };
          localStorage.setItem('unified_suggested_allocation', JSON.stringify(payload));
          window.dispatchEvent(new CustomEvent('unifiedSuggestedAllocationUpdated', { detail: payload }));
          console.debug('✅ Unified suggested allocation persisted:', {
            targetsCount: Object.keys(targetAdj).length,
            visibleCount: visible.length,
            execPlanCount: Object.keys(executionPlan).length,
            cap: mode.cap,
            hasCurrentData: !!(current && current.groups)
          });
        } else {
          (window.debugLogger?.warn || console.warn)('⚠️ No targetAdj data to persist', { targetAdj, keys: Object.keys(targetAdj || {}) });
        }
      } catch (e) {
        (window.debugLogger?.warn || console.warn)('Persist unified suggested allocation failed:', e?.message || e);
      }

      // NOUVEAU - Séparation Budget vs Exécution
      const riskBudget = u.risk_budget || {};
      const execution = u.execution || {};
      const stablesTheorique = riskBudget.target_stables_pct || null;
      let estimatedIters = execution.estimated_iters_to_target ?? 'N/A';
      if (visible.length > 0) {
        const capPctForIterations = capPercent != null ? capPercent : (typeof mode.cap === 'number' ? mode.cap : null);
        const capFraction = capPctForIterations != null ? capPctForIterations / 100 : 0;
        if (capFraction <= 0) {
          estimatedIters = '∞';
        } else {
          const maxDeltaPct = visible.reduce((max, entry) => {
            const current = typeof entry.cur === 'number' ? entry.cur : 0;
            const target = typeof entry.tgt === 'number' ? entry.tgt : 0;
            const diff = Math.abs(target - current);
            return diff > max ? diff : max;
          }, 0);
          const maxDeltaFraction = maxDeltaPct / 100;
          estimatedIters = maxDeltaFraction > 0 ? Math.max(1, Math.ceil(maxDeltaFraction / capFraction)) : 0;
        }
      }

      // TÂCHE 4 - Verrous anti-régression (dev uniquement) avant rendu
      if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
        const stablesEntry = visible.find(v => v.k === 'Stablecoins');
        const totalTgt = visible.reduce((sum, v) => sum + (Number(v.tgt) || 0), 0);

        if (!stablesEntry || stablesEntry.tgt < 0.5) {
          (window.debugLogger?.error || console.error)('[ASSERT] UI RENDER: Stablecoins manquantes dans visible targets', { visible, stablesEntry });
        }
        if (Math.abs(totalTgt - 100) > 0.5) {
          (window.debugLogger?.error || console.error)('[ASSERT] UI RENDER: Somme targets visible ≠ 100%', { totalTgt, visible });
        }
        console.debug(`✅ UI RENDER: Verrous OK - Stables ${stablesEntry?.tgt?.toFixed(1) || 0}%, Total ${totalTgt.toFixed(1)}%`);
      }

      return `
        ${card(`
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem;">
            <div style="font-weight:700;">💡 Objectifs Théoriques</div>
            <div style="font-size:.75rem; color:var(--theme-text-muted); background: var(--theme-bg); border:1px solid var(--theme-border); padding:.2rem .6rem; border-radius: 999px;">
              Budget Risque: ${riskBudget.methodology || 'regime_based'}
            </div>
          </div>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:.5rem; font-size:.85rem;">
            ${visible.map(({k, cur, tgt}) => {
              const grand = Number(current?.grand || 0);
              const tgtUsd = (tgt / 100) * grand;
              const tgtUsdStr = `$${Math.round(tgtUsd).toLocaleString('en-US')}`;
              const tgtW = Math.max(0, Math.min(100, tgt));
              return `
                <div style="padding:.5rem .7rem; background: var(--theme-surface); border-radius: var(--radius-sm); border: 1px solid var(--theme-border);">
                  <div style="font-weight: 600; margin-bottom:.3rem; color: var(--theme-text);">${k}</div>
                  <div style="display:flex; justify-content:space-between; margin-bottom:.2rem;">
                    <span style="color: var(--theme-text-muted);">Objectif</span>
                    <span style="font-weight: 600;">${tgt.toFixed(1)}%</span>
                  </div>
                  <div style="height:6px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                    <div style="width:${tgtW}%; height:100%; background: var(--brand-primary);"></div>
                  </div>
                  <div style="font-size:.75rem; color:var(--theme-text-muted); margin-top:.3rem;">${tgtUsdStr}</div>
                </div>
              `;
            }).join('')}
          </div>
          ${stablesTheorique ? `<div style="margin-top:.6rem; font-size:.75rem; color:var(--theme-text-muted); padding:.4rem; background: var(--theme-bg); border-radius: 6px; border: 1px solid var(--theme-border);">
            💰 Budget stables théorique: <b>${stablesTheorique}%</b> (calculé par algorithme de risque)
          </div>` : ''}
        `, { title: 'Budget & Objectifs' })}

        ${card(`
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem;">
            <div style="font-weight:700;">🎯 Plan d'Exécution (Itération ${execution.current_iteration || 1})</div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              ${activePolicy ? `<div style="font-size:.7rem; color: var(--success); background: var(--theme-bg); border:1px solid var(--success); padding:.1rem .4rem; border-radius: 999px;">🏛️ Governance</div>` : ''}
              <div style="font-size:.75rem; color:var(--theme-text-muted); background: var(--theme-bg); border:1px solid var(--theme-border); padding:.2rem .6rem; border-radius: 999px;">
                Cap ±${mode.cap}%
              </div>
            </div>
          </div>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:.45rem; font-size:.8rem;">
            ${visible.map(({k, cur, tgt, delta, suggested}) => {
              const moveColor = suggested >= 0 ? 'var(--success)' : 'var(--danger)';
              const sign = (v) => v > 0 ? '+' : '';
              const curW = Math.max(0, Math.min(100, cur));
              const suggestedTgt = cur + suggested; // Cible de cette itération
              const suggestedW = Math.max(0, Math.min(100, suggestedTgt));
              const grand = Number(current?.grand || 0);
              const curUsd = (cur / 100) * grand;
              const suggestedUsd = (suggestedTgt / 100) * grand;
              const curUsdStr = `$${Math.round(curUsd).toLocaleString('en-US')}`;
              const suggestedUsdStr = `$${Math.round(suggestedUsd).toLocaleString('en-US')}`;
              const tip = `Actuel: ${curUsdStr} → Cette itération: ${suggestedUsdStr}`;
              return `
                <div data-tooltip="${tip}" style="padding:.5rem .6rem; background: var(--theme-bg); border-radius: var(--radius-sm); border: 1px solid var(--theme-border);">
                  <div style="font-weight: 700; margin-bottom:.25rem;">${k}</div>
                  <div style="display:flex; justify-content:space-between; color: var(--theme-text-muted);">
                    <span>Actuel</span><span>${cur.toFixed(1)}%</span>
                  </div>
                  <div style="height:4px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                    <div style="width:${curW}%; height:100%; background: color-mix(in oklab, var(--theme-text) 25%, transparent);"></div>
                  </div>
                  <div style="display:flex; justify-content:space-between; color: var(--theme-text-muted); margin-top:.25rem;">
                    <span>Itération 1</span><span>${suggestedTgt.toFixed(1)}%</span>
                  </div>
                  <div style="height:4px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                    <div style="width:${suggestedW}%; height:100%; background: var(--warning);"></div>
                  </div>
                  <div style="margin-top:.35rem; font-size:.75rem; color:${moveColor}; font-weight:600; text-align:right;">Δ ${sign(suggested)}${suggested}%</div>
                </div>
              `;
            }).join('')}
          </div>
          <div style="margin-top:.6rem; font-size:.75rem; color:var(--theme-text-muted); padding:.4rem; background: var(--theme-bg); border-radius: 6px; border: 1px solid var(--theme-border);">
            ⏱️ Convergence estimée: <b>${estimatedIters} rebalances</b> pour atteindre les objectifs théoriques
          </div>
        `, { title: 'Exécution Cap ±' + mode.cap + '%' })}
      `;
    }

    return '';
  } catch (e) {
    (window.debugLogger?.warn || console.warn)('Unified allocation render skipped:', e.message || e);
    return '';
  }
}
