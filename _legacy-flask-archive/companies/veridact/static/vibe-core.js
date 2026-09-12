/**
 * OTT VIBE CORE v1.0 — Veridact Enhancements
 * Adds ⌘K Command Palette, App Switcher, Toast Feedback, and Smooth Micro-interactions
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('vibe-enabled');
  });

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

    const indicatorColor = type === 'success' ? '#22C55E' : type === 'error' ? '#DC2626' : '#7C3AED';
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
