/**
 * OTT VIBE CORE v1.0 — Universal Interactive Enhancements
 * Adds ⌘K Command Palette, App Switcher, Toast Feedback, and Smooth Micro-interactions
 */

(function () {
  'use strict';

  // 1. Enable Vibe Aesthetics on Body
  document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('vibe-enabled');
    initCommandPalette();
    initGlobalShortcuts();
  });

  // App Switcher Registry (Ports & Names)
  const OTT_APPS = [
    { name: 'Veridact (Capture Attestation)', port: 5102, accent: '#7C3AED', category: 'Sovereign' },
    { name: 'Canonchain (IP Merkle Registry)', port: 5101, accent: '#F59E0B', category: 'Sovereign' },
    { name: 'Clearpath (Compliance Rules Engine)', port: 5104, accent: '#10B981', category: 'Sovereign' },
    { name: 'Sovereign Edit (Film Provenance)', port: 5105, accent: '#6366F1', category: 'Sovereign' },
    { name: 'Strata Finance (Waterfall Ledger)', port: 5106, accent: '#059669', category: 'Sovereign' },
    { name: 'ContextCore (Local RAG Graph)', port: 5107, accent: '#10B981', category: 'Sovereign' },
    { name: 'Story Atlas (Canon Engine)', port: 5109, accent: '#C1121F', category: 'CreativeOS' },
    { name: 'FrameVault (Identity & IP Root)', port: 5001, accent: '#E5482D', category: 'CreativeOS' },
    { name: 'FilmCrew (Production Marketplace)', port: 5002, accent: '#0891B2', category: 'CreativeOS' },
    { name: 'RightsForge (IP Optioning & Licensing)', port: 5003, accent: '#65A30D', category: 'CreativeOS' },
    { name: 'CreatorStack (Bounties & Challenges)', port: 5005, accent: '#DB2777', category: 'CreativeOS' },
    { name: 'OTT Studio (Creative Workspaces)', port: 5006, accent: '#4F46E5', category: 'CreativeOS' },
    { name: 'DB Viewer (Database Inspector)', port: 5900, accent: '#3B82F6', category: 'Infra' }
  ];

  // 2. Command Palette Implementation
  function initCommandPalette() {
    // Inject Overlay HTML if not present
    if (document.getElementById('vibe-cmd-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'vibe-cmd-overlay';
    overlay.className = 'vibe-cmd-overlay';
    overlay.innerHTML = `
      <div class="vibe-cmd-modal">
        <div class="vibe-cmd-input-wrap">
          <span style="margin-right: 10px; color: var(--muted);">⌘</span>
          <input type="text" id="vibe-cmd-input" class="vibe-cmd-input" placeholder="Search products, actions, ports..." autocomplete="off">
          <span class="vibe-kbd">ESC</span>
        </div>
        <div id="vibe-cmd-results" class="vibe-cmd-results"></div>
      </div>
    `;
    document.body.appendChild(overlay);

    const input = document.getElementById('vibe-cmd-input');
    const results = document.getElementById('vibe-cmd-results');

    function renderResults(query = '') {
      results.innerHTML = '';
      const filtered = OTT_APPS.filter(app => 
        app.name.toLowerCase().includes(query.toLowerCase()) || 
        app.port.toString().includes(query)
      );

      if (filtered.length === 0) {
        results.innerHTML = `<div style="padding: 1rem; color: var(--muted); text-align: center;">No matching applications found</div>`;
        return;
      }

      filtered.forEach((app, idx) => {
        const item = document.createElement('div');
        item.className = `vibe-cmd-item ${idx === 0 ? 'selected' : ''}`;
        item.innerHTML = `
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="vibe-dot" style="background: ${app.accent};"></span>
            <span>${app.name}</span>
          </div>
          <span class="vibe-kbd">Port ${app.port}</span>
        `;
        item.addEventListener('click', () => {
          window.location.href = `http://localhost:${app.port}`;
        });
        results.appendChild(item);
      });
    }

    input.addEventListener('input', (e) => renderResults(e.target.value));

    // Keyboard Navigation in Cmd Palette
    input.addEventListener('keydown', (e) => {
      const items = Array.from(results.querySelectorAll('.vibe-cmd-item'));
      const activeIdx = items.findIndex(el => el.classList.contains('selected'));

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (items.length) {
          items[activeIdx]?.classList.remove('selected');
          const next = items[(activeIdx + 1) % items.length];
          next.classList.add('selected');
          next.scrollIntoView({ block: 'nearest' });
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (items.length) {
          items[activeIdx]?.classList.remove('selected');
          const prev = items[(activeIdx - 1 + items.length) % items.length];
          prev.classList.add('selected');
          prev.scrollIntoView({ block: 'nearest' });
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const selected = items[activeIdx];
        if (selected) selected.click();
      }
    });

    // Close on Backdrop Click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) toggleCmdPalette(false);
    });
  }

  function toggleCmdPalette(show) {
    const overlay = document.getElementById('vibe-cmd-overlay');
    const input = document.getElementById('vibe-cmd-input');
    if (!overlay) return;

    if (show === undefined) show = !overlay.classList.contains('active');

    if (show) {
      overlay.classList.add('active');
      input.value = '';
      input.focus();
      // Render initial list
      const event = new Event('input');
      input.dispatchEvent(event);
    } else {
      overlay.classList.remove('active');
    }
  }

  // 3. Global Shortcuts (⌘K, Escape)
  function initGlobalShortcuts() {
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggleCmdPalette();
      } else if (e.key === 'Escape') {
        toggleCmdPalette(false);
      }
    });
  }

  // 4. Toast Notification Utility
  window.vibeToast = function (message, type = 'info') {
    let container = document.getElementById('vibe-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'vibe-toast-container';
      container.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 10000;
        display: flex; flex-direction: column; gap: 8px; pointer-events: none;
      `;
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'vibe-card';
    toast.style.cssText = `
      padding: 10px 16px; font-size: 0.85rem; font-family: 'Space Grotesk', sans-serif;
      display: flex; align-items: center; gap: 10px; pointer-events: auto;
      transform: translateY(20px); opacity: 0; transition: all 220ms cubic-bezier(0.16, 1, 0.3, 1);
    `;

    const indicatorColor = type === 'success' ? '#22C55E' : type === 'error' ? '#DC2626' : 'var(--ott-signature)';
    toast.innerHTML = `
      <span class="vibe-dot" style="background: ${indicatorColor};"></span>
      <span>${message}</span>
    `;

    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.transform = 'translateY(0)';
      toast.style.opacity = '1';
    });

    setTimeout(() => {
      toast.style.transform = 'translateY(10px)';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 250);
    }, 3000);
  };
})();
