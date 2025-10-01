// static/components/risk-snapshot.js
// Web Component Data pour affichage Risk avec store subscribe + fallback API polling

import { fetchRisk, waitForGlobalEventOrTimeout, fallbackSelectors } from './utils.js';

const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const pct = (x, d = 0) => Number.isFinite(x) ? (x * 100).toFixed(d) + '%' : '—';

// Import sélecteurs asynchrone (compatible sans top-level await)
const selectorsPromise = import('../selectors/governance.js').catch(() => null);

/**
 * @typedef {Object} RiskState
 * @property {Object} governance
 * @property {number} [governance.contradiction_index] - 0..1 ou 0..100
 * @property {number} [governance.cap_daily] - 0..1
 * @property {string} [governance.ml_signals_timestamp] - ISO
 * @property {Object} [scores]
 * @property {number} [scores.ccs]
 * @property {number} [scores.onchain]
 * @property {number} [scores.risk]
 * @property {number} [scores.blended]
 * @property {Array}  [alerts]
 */

class RiskSnapshot extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.title = this.getAttribute('title') || 'Risk Snapshot';
    this.pollMs = Number(this.getAttribute('poll-ms') || 30000); // 0 => pas de polling
    this.include = {
      ccs: this.hasAttribute('include-ccs'),
      onchain: this.hasAttribute('include-onchain'),
      risk: this.hasAttribute('include-risk'),
      blended: this.hasAttribute('include-blended'),
      alerts: this.hasAttribute('include-alerts'),
    };
    this._prevContradiction = null;
    this._unsub = null;
    this._poll = null;
  }

  connectedCallback() {
    this._render();
    this._afterConnect();
  }

  disconnectedCallback() {
    if (typeof this._unsub === 'function') {
      this._unsub();
      this._unsub = null;
    }
    if (this._poll) {
      clearInterval(this._poll);
      this._poll = null;
    }
  }

  async _afterConnect() {
    this.$ = {
      title: this.shadowRoot.querySelector('#title'),
      regime: this.shadowRoot.querySelector('#regime'),
      cTxt: this.shadowRoot.querySelector('#c-txt'),
      cBar: this.shadowRoot.querySelector('#c-bar'),
      cap: this.shadowRoot.querySelector('#cap'),
      trend: this.shadowRoot.querySelector('#trend'),
      fresh: this.shadowRoot.querySelector('#fresh'),
      fdot: this.shadowRoot.querySelector('#fdot'),
      // sections étendues, déjà présentes mais cachées par défaut
      extCCS: this.shadowRoot.querySelector('#ext-ccs'),
      extOnchain: this.shadowRoot.querySelector('#ext-onchain'),
      extRisk: this.shadowRoot.querySelector('#ext-risk'),
      extBlended: this.shadowRoot.querySelector('#ext-blended'),
      extAlerts: this.shadowRoot.querySelector('#ext-alerts'),
    };
    this.$.title.textContent = this.title;

    const selMod = await selectorsPromise;
    this._selectors = selMod ? {
      selectContradiction01: selMod.selectContradiction01,
      selectCapPercent: selMod.selectCapPercent,
      selectGovernanceTimestamp: selMod.selectGovernanceTimestamp,
    } : fallbackSelectors;

    if (window.riskStore?.subscribe) {
      this._connectStore();
      return;
    }

    const ready = await waitForGlobalEventOrTimeout('riskStoreReady', 1500);
    if (ready && window.riskStore?.subscribe) {
      this._connectStore();
      return;
    }

    if (this.pollMs > 0) {
      await this._pollOnce();
      this._poll = setInterval(() => this._pollOnce(), this.pollMs);
    }
  }

  _connectStore() {
    const push = () => {
      const state = window.riskStore?.getState?.() || {};
      this._updateFromState(state);
    };
    push();
    this._unsub = window.riskStore.subscribe(push);
  }

  async _pollOnce() {
    this._setLoading(true);
    const j = await fetchRisk();
    this._setLoading(false);

    if (!j) {
      this._setError('API indisponible');
      return;
    }

    this._setError(null);
    const state = { governance: j?.governance || j?.risk?.governance || {} };
    this._updateFromState(state);
  }

  _setLoading(on) {
    if (this.$?.title) this.$.title.style.opacity = on ? '0.6' : '1';
  }

  _setError(msg) {
    if (!this.$?.trend) return;
    if (msg) {
      this.$.trend.textContent = '⚠';
      this.$.trend.title = msg;
    } else {
      this.$.trend.title = '';
    }
  }

  _computeTrend(curr) {
    const prev = this._prevContradiction;
    this._prevContradiction = curr;
    if (!Number.isFinite(prev)) return '→';
    const delta = curr - prev;
    if (Math.abs(delta) < 0.05) return '→';
    return delta > 0 ? '↗' : '↘';
  }

  _updateFromState(/** @type {RiskState} */ s) {
    const c01 = clamp(this._selectors.selectContradiction01(s));
    const cap = this._selectors.selectCapPercent(s);
    const ts = this._selectors.selectGovernanceTimestamp(s);

    this.$.cTxt.textContent = pct(c01, 0);
    this.$.cBar.style.width = (c01 * 100).toFixed(0) + '%';
    this.$.cap.textContent = Number.isFinite(cap) ? (cap * 100).toFixed(2) + '%' : '—';

    let freshTxt = '—', dot = '';
    if (ts) {
      const t = new Date(ts).getTime();
      const min = (Date.now() - t) / 60000;
      freshTxt = min < 2 ? 'Temps réel' : `${min.toFixed(0)} min`;
      dot = min < 5 ? 'ok' : (min < 60 ? 'warn' : 'danger');
    }
    this.$.fresh.textContent = freshTxt;
    this.$.fdot.className = 'dot ' + dot;

    this.$.trend.textContent = this._computeTrend(c01);
    const regime = (c01 < 0.3 && cap >= 0.01) ? 'Euphorie' : (c01 > 0.7 ? 'Stress' : 'Neutre');
    this.$.regime.textContent = regime;

    // Sections étendues (si un jour on branche des scores additionnels)
    if (this.include.ccs && this.$.extCCS) this.$.extCCS.hidden = false;
    if (this.include.onchain && this.$.extOnchain) this.$.extOnchain.hidden = false;
    if (this.include.risk && this.$.extRisk) this.$.extRisk.hidden = false;
    if (this.include.blended && this.$.extBlended) this.$.extBlended.hidden = false;
    if (this.include.alerts && this.$.extAlerts) this.$.extAlerts.hidden = false;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --card-bg: var(--theme-surface, #0f1115);
          --card-fg: var(--theme-fg, #e5e7eb);
          --card-border: var(--theme-border, #2a2f3b);
        }

        .card {
          border: 1px solid var(--card-border);
          background: var(--card-bg);
          color: var(--card-fg);
          border-radius: 12px;
          overflow: hidden;
        }

        .header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          border-bottom: 1px solid var(--card-border);
        }

        .title {
          font-weight: 600;
          font-size: 14px;
          letter-spacing: .2px;
          flex: 1;
        }

        .badge {
          font-size: 11px;
          padding: 4px 8px;
          border-radius: 999px;
          background: #1f2937;
          border: 1px solid #374151;
        }

        .body {
          padding: 10px 12px;
          display: grid;
          gap: 10px;
        }

        .row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }

        .kv {
          display: flex;
          align-items: baseline;
          gap: 8px;
        }

        .k {
          font-size: 12px;
          color: #9ca3af;
        }

        .v {
          font-size: 14px;
          font-weight: 600;
        }

        .progress {
          height: 8px;
          border-radius: 999px;
          background: #1f2937;
          overflow: hidden;
          flex: 1;
          border: 1px solid var(--card-border);
        }

        .progress i {
          display: block;
          height: 100%;
          width: 0%;
          background: #3b82f6;
          transition: width .35s ease;
        }

        .dot {
          width: 8px;
          height: 8px;
          border-radius: 999px;
          display: inline-block;
          margin-right: 6px;
          background: #6b7280;
        }

        .dot.ok {
          background: #10b981;
        }

        .dot.warn {
          background: #f59e0b;
        }

        .dot.danger {
          background: #ef4444;
        }

        .extended {
          opacity: .9;
        }
      </style>

      <div class="card">
        <div class="header">
          <div class="title" id="title">Risk Snapshot</div>
          <span class="badge" id="regime">—</span>
        </div>
        <div class="body">
          <div class="row">
            <div class="kv">
              <div class="k">Contradiction</div>
              <div class="v" id="c-txt">—</div>
            </div>
            <div class="progress"><i id="c-bar"></i></div>
          </div>
          <div class="row">
            <div class="kv">
              <div class="k">Cap journalier</div>
              <div class="v" id="cap">—</div>
            </div>
            <div class="kv">
              <div class="k">Trend</div>
              <div class="v" id="trend">→</div>
            </div>
          </div>
          <div class="row">
            <div class="kv">
              <div class="k">Fraîcheur</div>
              <div class="v"><i class="dot" id="fdot"></i><span id="fresh">—</span></div>
            </div>
          </div>

          <!-- Sections étendues (déjà en place, masquées par défaut) -->
          <div class="row extended" id="ext-ccs" hidden>
            <div class="kv">
              <div class="k">CCS Mixte</div>
              <div class="v">—</div>
            </div>
          </div>
          <div class="row extended" id="ext-onchain" hidden>
            <div class="kv">
              <div class="k">On-Chain</div>
              <div class="v">—</div>
            </div>
          </div>
          <div class="row extended" id="ext-risk" hidden>
            <div class="kv">
              <div class="k">Risk</div>
              <div class="v">—</div>
            </div>
          </div>
          <div class="row extended" id="ext-blended" hidden>
            <div class="kv">
              <div class="k">Blended</div>
              <div class="v">—</div>
            </div>
          </div>
          <div class="row extended" id="ext-alerts" hidden>
            <div class="kv">
              <div class="k">Alerts</div>
              <div class="v">—</div>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('risk-snapshot', RiskSnapshot);
export { RiskSnapshot };
