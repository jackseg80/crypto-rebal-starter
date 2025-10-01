// static/components/flyout-panel.js
// Web Component UI pour flyout panel overlay avec handle, pin/unpin, theme hérité

import { ns } from './utils.js';

class FlyoutPanel extends HTMLElement {
  static get observedAttributes() {
    return ['position', 'width', 'persist-key', 'pinned'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.state = {
      position: 'left',
      width: 340,
      key: 'flyout',
      pinned: false
    };
  }

  connectedCallback() {
    this._render();
    this._mount();
  }

  disconnectedCallback() {
    this._unbind();
  }

  attributeChangedCallback(name, _, v) {
    if (name === 'position') this.state.position = (v === 'right' ? 'right' : 'left');
    if (name === 'width') this.state.width = Number(v) || 340;
    if (name === 'persist-key') this.state.key = v || 'flyout';
    if (name === 'pinned') this.state.pinned = this.hasAttribute('pinned');
    this._apply();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          /* Thème hérité via variables CSS parentes */
          --flyout-bg: var(--theme-surface, #0f1115);
          --flyout-fg: var(--theme-fg, #e5e7eb);
          --flyout-border: var(--theme-border, #2a2f3b);
          --flyout-blur: var(--theme-blur, 8px);
          --flyout-width: ${this.state.width}px;
          --flyout-handle-width: 48px;
          --flyout-padding: 12px;
          --flyout-font-size: 0.95rem;
        }

        /* Responsive mobile */
        @media (max-width: 768px) {
          :host {
            --flyout-width: 280px;
            --flyout-handle-width: 36px;
            --flyout-padding: 12px;
            --flyout-font-size: 0.875rem;
          }
        }

        .flyout {
          position: fixed;
          top: 120px;
          left: 0;
          width: var(--flyout-width);
          max-height: calc(100vh - 140px);
          color: var(--flyout-fg);
          backdrop-filter: blur(16px) saturate(1.8);
          background: color-mix(in srgb, var(--flyout-bg) 88%, transparent 12%);
          border: 1px solid color-mix(in srgb, var(--flyout-border) 45%, transparent);
          border-left: none;
          border-radius: 0 var(--radius-xl, 12px) var(--radius-xl, 12px) 0;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
          transform: translateX(calc(-100% + var(--flyout-handle-width)));
          transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.3s ease;
          opacity: 0.5;
          display: grid;
          grid-template-rows: auto 1fr;
          z-index: 25;
          font-size: var(--flyout-font-size);
          overflow: hidden;
        }

        .flyout.right {
          left: auto;
          right: 0;
          border-right: none;
          border-left: 1px solid var(--flyout-border);
          transform: translateX(calc(100% - var(--flyout-handle-width)));
        }

        .flyout.open,
        .flyout.pinned {
          transform: translateX(0);
          opacity: 1;
        }

        .handle {
          position: absolute;
          top: 50%;
          transform: translateY(-50%);
          right: -48px;
          width: var(--flyout-handle-width);
          padding: var(--space-md, 12px) var(--space-xs, 6px);
          background: var(--brand-primary, #3b82f6);
          color: white;
          border: none;
          border-radius: 0 var(--radius-lg, 8px) var(--radius-lg, 8px) 0;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
          display: grid;
          place-items: center;
          cursor: pointer;
          font-size: 0.75rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          writing-mode: vertical-rl;
          text-orientation: mixed;
          opacity: 0.85;
          transition: opacity 0.2s ease;
          pointer-events: auto;
        }

        .flyout.right .handle {
          left: -1px;
          right: auto;
          border-left: 1px solid var(--flyout-border);
          border-right: none;
          border-radius: 8px 0 0 8px;
        }

        .flyout.open .handle,
        .flyout.pinned .handle {
          opacity: 0;
          pointer-events: none;
        }

        header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px var(--flyout-padding);
          border-bottom: 1px solid var(--flyout-border);
          background: color-mix(in oklab, var(--flyout-bg) 92%, transparent);
        }

        .title {
          font-weight: 600;
          letter-spacing: .2px;
          flex: 1;
        }

        .actions {
          display: flex;
          gap: 6px;
        }

        button {
          width: 28px;
          height: 28px;
          display: grid;
          place-items: center;
          background: #151c29;
          border: 1px solid var(--flyout-border);
          border-radius: 8px;
          color: #9ca3af;
          cursor: pointer;
        }

        button:hover {
          background: #1a2233;
          color: #e5e7eb;
        }

        main {
          overflow: auto;
          padding: var(--flyout-padding);
        }
      </style>

      <div class="flyout" role="complementary" aria-label="Flyout panel" aria-expanded="false">
        <div class="handle" title="Ouvrir">≡</div>
        <header>
          <div class="title"><slot name="title">Panel</slot></div>
          <div class="actions">
            <button id="pin" title="Épingler" aria-pressed="false">📍</button>
            <button id="close" title="Fermer">✕</button>
          </div>
        </header>
        <main>
          <slot name="content"></slot>
        </main>
      </div>
    `;
  }

  _mount() {
    this.$ = {
      root: this.shadowRoot.querySelector('.flyout'),
      handle: this.shadowRoot.querySelector('.handle'),
      pin: this.shadowRoot.querySelector('#pin'),
      close: this.shadowRoot.querySelector('#close')
    };

    // Load persisted state
    const persisted = JSON.parse(localStorage.getItem(ns(this.state.key)) || '{}');
    if (typeof persisted.pinned === 'boolean') this.state.pinned = persisted.pinned;

    // Event handlers
    this._onEnter = () => {
      if (!this.state.pinned) {
        this.$.root.classList.add('open');
        this._apply();
      }
    };

    this._onLeave = () => {
      if (!this.state.pinned) {
        this.$.root.classList.remove('open');
        this._apply();
      }
    };

    this._onPin = () => {
      this.state.pinned = !this.state.pinned;
      this._persist();
      this._apply();
    };

    this._onClose = () => {
      if (!this.state.pinned) {
        this.$.root.classList.remove('open');
        this._apply();
      }
    };

    this._onKey = (e) => {
      if (e.key === 'Escape') this._onClose();
    };

    // Bind events
    this.$.handle.addEventListener('mouseenter', this._onEnter);
    this.$.root.addEventListener('mouseleave', this._onLeave);
    this.$.pin.addEventListener('click', this._onPin);
    this.$.close.addEventListener('click', this._onClose);
    document.addEventListener('keydown', this._onKey);

    this._apply();
  }

  _unbind() {
    this.$?.handle.removeEventListener('mouseenter', this._onEnter);
    this.$?.root.removeEventListener('mouseleave', this._onLeave);
    this.$?.pin.removeEventListener('click', this._onPin);
    this.$?.close.removeEventListener('click', this._onClose);
    document.removeEventListener('keydown', this._onKey);
  }

  _persist() {
    localStorage.setItem(ns(this.state.key), JSON.stringify({ pinned: this.state.pinned }));
  }

  _apply() {
    if (!this.$) return;

    const isOpen = this.state.pinned || this.$.root.classList.contains('open');

    this.$.root.classList.toggle('right', this.state.position === 'right');
    this.$.root.classList.toggle('pinned', !!this.state.pinned);

    // ARIA attributes
    this.$.root.setAttribute('aria-expanded', String(isOpen));
    this.$.pin.textContent = this.state.pinned ? '📌' : '📍';
    this.$.pin.setAttribute('aria-pressed', String(!!this.state.pinned));

    // Dynamic width
    this.style.setProperty('--flyout-width', `${this.state.width}px`);
  }
}

customElements.define('flyout-panel', FlyoutPanel);
export { FlyoutPanel };
