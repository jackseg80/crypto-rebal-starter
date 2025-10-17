// UnifiedInsights - Phase Engine Diagnostics Panel
// Renders the Phase Engine diagnostics and controls

import { card } from './utils.js';

/**
 * Renders the Phase Engine diagnostics panel
 */
export function renderPhaseEnginePanel() {
  const rawPhaseMode = localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow';
  const phaseMode = rawPhaseMode.toLowerCase();
  const isDisabled = phaseMode === 'off' || phaseMode === 'disabled' || phaseMode === 'disable';
  const phaseModeBadge = isDisabled ? 'DISABLED' : rawPhaseMode.toUpperCase();
  const shadowResult = typeof window !== 'undefined' ? window._phaseEngineShadowResult : null;
  const phaseConfig = typeof window !== 'undefined' ? window._phaseEngineConfig : null;

  return card(`
    <div style="font-weight:700; margin-bottom:.5rem; display: flex; align-items: center; gap: .5rem;">
      🧪 Phase Engine Diagnostics
      <span style="background: var(--info); color: white; padding: 1px 6px; border-radius: 3px; font-size: .7rem; font-weight: 700;">${phaseModeBadge}</span>
    </div>

    ${isDisabled ? `
      <div style="margin-bottom: .75rem; font-size: .8rem; color: var(--theme-text-muted);">
        Phase engine disabled. Use the controls below to re-enable diagnostics.
      </div>
    ` : ''}

    ${shadowResult ? `
      <div style="margin-bottom: .75rem;">
        <div style="font-weight: 600; margin-bottom: .25rem;">Current Detection:</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: .5rem; font-size: .8rem;">
          <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
            <div style="font-weight: 600; color: var(--brand-primary);">${shadowResult.phase.replace('_', ' ').toUpperCase()}</div>
            <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">Phase</div>
          </div>
          <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
            <div style="font-weight: 600;">${shadowResult.inputs.DI.toFixed(1)}</div>
            <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">DI Score</div>
          </div>
          <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
            <div style="font-weight: 600;">${(shadowResult.inputs.breadth_alts * 100).toFixed(1)}%</div>
            <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">Breadth</div>
          </div>
          <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
            <div style="font-weight: 600;">${shadowResult.inputs.partial ? 'Partial' : 'Complete'}</div>
            <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">Data Quality</div>
          </div>
        </div>
      </div>

      ${shadowResult.metadata.tiltsApplied ? `
        <div style="margin-bottom: .75rem;">
          <div style="font-weight: 600; margin-bottom: .25rem;">Applied Tilts:</div>
          <div style="font-size: .8rem; color: var(--theme-text);">
            ${Object.entries(shadowResult.metadata.tilts || {}).map(([asset, mult]) =>
              `<span style="margin-right: .5rem; background: var(--theme-surface); padding: .2rem .4rem; border-radius: 3px;">${asset}: ×${mult}</span>`
            ).join('')}
          </div>
          ${shadowResult.metadata.capsTriggered.length > 0 ? `
            <div style="margin-top: .5rem; font-size: .75rem; color: var(--warning);">
              🧢 Caps triggered: ${shadowResult.metadata.capsTriggered.join(', ')}
            </div>
          ` : ''}
          ${shadowResult.metadata.stablesFloorHit ? `
            <div style="margin-top: .25rem; font-size: .75rem; color: var(--info);">
              🏛️ Stables floor applied
            </div>
          ` : ''}
        </div>
      ` : ''}

      <div style="margin-bottom: .75rem;">
        <div style="font-weight: 600; margin-bottom: .25rem;">Phase Series Data:</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: .5rem; font-size: .75rem;">
          <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
            ETH/BTC: ${shadowResult.inputs.eth_btc.length} samples
          </div>
          <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
            Alts/BTC: ${shadowResult.inputs.alts_btc.length} samples
          </div>
          <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
            BTC Dom: ${(shadowResult.inputs.btc_dom * 100).toFixed(1)}%
          </div>
          <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
            Dispersion: ${(shadowResult.inputs.dispersion * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <div style="font-size: .7rem; color: var(--theme-text-muted); margin-bottom: .5rem;">
        Last update: ${new Date(shadowResult.timestamp).toLocaleTimeString()}
      </div>
    ` : ''}

    <div style="display: flex; gap: .5rem; flex-wrap: wrap;">
      <button onclick="localStorage.setItem('PHASE_ENGINE_ENABLED', 'shadow'); location.reload();"
              style="padding: .3rem .6rem; border: 1px solid var(--info); background: ${phaseMode === 'shadow' ? 'var(--info)' : 'transparent'}; color: ${phaseMode === 'shadow' ? 'white' : 'var(--info)'}; border-radius: var(--radius-sm); font-size: .75rem; cursor: pointer;">
        Shadow Mode
      </button>
      <button onclick="localStorage.setItem('PHASE_ENGINE_ENABLED', 'apply'); location.reload();"
              style="padding: .3rem .6rem; border: 1px solid var(--warning); background: ${phaseMode === 'apply' ? 'var(--warning)' : 'transparent'}; color: ${phaseMode === 'apply' ? 'white' : 'var(--warning)'}; border-radius: var(--radius-sm); font-size: .75rem; cursor: pointer;">
        Apply Mode
      </button>
      <button onclick="localStorage.setItem('PHASE_ENGINE_ENABLED', 'off'); location.reload();"
              style="padding: .3rem .6rem; border: 1px solid var(--theme-text-muted); background: ${isDisabled ? 'var(--theme-text-muted)' : 'transparent'}; color: ${isDisabled ? 'white' : 'var(--theme-text-muted)'}; border-radius: var(--radius-sm); font-size: .75rem; cursor: pointer;">
        Disabled
      </button>
    </div>

    <div style="margin-top: .5rem; padding: .4rem; background: var(--theme-surface); border-radius: var(--radius-sm); font-size: .7rem; color: var(--theme-text-muted);">
      <strong>Shadow Mode:</strong> Calculate phase tilts but don't apply them (logging only)<br>
      <strong>Apply Mode:</strong> Actually use phase-tilted targets for allocation<br>
      <strong>Disabled:</strong> Use standard dynamic targets without phase engine
    </div>
  `, { title: 'Phase Engine Beta' });
}
