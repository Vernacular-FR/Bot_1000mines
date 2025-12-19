/**
 * Bot Overlay UI - Template JavaScript
 * 
 * Injecté dans la page 1000mines.com pour afficher les overlays du solver.
 * API exposée via window.BotOverlay
 */

(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    CELL_SIZE: 24,
    CELL_BORDER: 1,
    UPDATE_INTERVAL: 16, // ~60 FPS
    Z_INDEX_OVERLAY: 9999,
    Z_INDEX_MENU: 10000,
  };

  // Couleurs par statut/type
  const COLORS = {
    // Focus levels
    TO_PROCESS: 'rgba(255, 165, 0, 0.4)',      // Orange
    PROCESSED: 'rgba(255, 255, 0, 0.3)',       // Jaune transparent
    TO_REDUCE: 'rgba(0, 120, 255, 0.4)',       // Bleu
    REDUCED: 'rgba(0, 180, 255, 0.3)',         // Bleu clair transparent
    
    // Statuts
    ACTIVE: 'rgba(0, 120, 255, 0.4)',
    FRONTIER: 'rgba(255, 165, 0, 0.4)',
    SOLVED: 'rgba(0, 255, 0, 0.2)',
    MINE: 'rgba(255, 0, 0, 0.4)',
    
    // Actions
    SAFE: 'rgba(0, 255, 0, 0.8)',
    FLAG: 'rgba(255, 0, 0, 0.8)',
    GUESS: 'rgba(255, 255, 255, 0.8)',
  };

  // État global
  const state = {
    currentOverlay: 'off',
    data: {
      frontier: null,
      actions: null,
      status: null,
    },
    anchorElement: null,
    overlayContainer: null,
    svgElement: null,
    menuElement: null,
    updateTimer: null,
  };

  /**
   * Initialisation de l'overlay UI
   */
  function init() {
    console.log('[BotOverlay] Initialisation...');
    
    // Trouver l'élément anchor
    state.anchorElement = document.getElementById('anchor');
    if (!state.anchorElement) {
      console.error('[BotOverlay] Élément #anchor introuvable');
      return false;
    }

    // Créer la structure HTML
    createOverlayStructure();
    
    // Démarrer la synchronisation
    startSyncLoop();
    
    console.log('[BotOverlay] Initialisé avec succès');
    return true;
  }

  /**
   * Crée la structure HTML/SVG de l'overlay
   */
  function createOverlayStructure() {
    // Container principal
    state.overlayContainer = document.createElement('div');
    state.overlayContainer.id = 'bot-overlay-container';
    state.overlayContainer.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: ${CONFIG.Z_INDEX_OVERLAY};
      overflow: hidden;
    `;

    // SVG overlay
    state.svgElement = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    state.svgElement.id = 'bot-overlay-svg';
    state.svgElement.style.cssText = `
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    `;

    // Groupes SVG pour les différentes couches
    const layers = ['grid', 'zones', 'actions'];
    layers.forEach(layer => {
      const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      group.id = `overlay-${layer}`;
      state.svgElement.appendChild(group);
    });

    state.overlayContainer.appendChild(state.svgElement);

    // Menu de contrôle
    state.menuElement = createMenu();
    state.overlayContainer.appendChild(state.menuElement);

    // Ajouter au DOM
    document.body.appendChild(state.overlayContainer);
  }

  /**
   * Crée le menu de sélection des overlays
   */
  function createMenu() {
    const menu = document.createElement('div');
    menu.id = 'bot-overlay-menu';
    menu.style.cssText = `
      position: fixed;
      top: 80px;
      right: 20px;
      background: rgba(0, 0, 0, 0.85);
      border: 2px solid rgba(255, 255, 255, 0.2);
      border-radius: 8px;
      padding: 12px;
      pointer-events: auto;
      z-index: ${CONFIG.Z_INDEX_MENU};
      font-family: system-ui, -apple-system, sans-serif;
      color: white;
      min-width: 150px;
    `;

    // Titre
    const title = document.createElement('div');
    title.textContent = 'Bot Overlays';
    title.style.cssText = `
      font-weight: bold;
      margin-bottom: 8px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.2);
      font-size: 14px;
    `;
    menu.appendChild(title);

    // Boutons
    const overlays = [
      { id: 'off', label: 'Off', icon: '○' },
      { id: 'frontier', label: 'Frontier', icon: '◉' },
      { id: 'actions', label: 'Actions', icon: '▶' },
      { id: 'status', label: 'Status', icon: '◆' },
    ];

    overlays.forEach(overlay => {
      const btn = document.createElement('button');
      btn.id = `overlay-btn-${overlay.id}`;
      btn.dataset.overlay = overlay.id;
      btn.textContent = `${overlay.icon} ${overlay.label}`;
      btn.style.cssText = `
        display: block;
        width: 100%;
        padding: 8px 12px;
        margin: 4px 0;
        background: ${overlay.id === 'off' ? 'rgba(255, 255, 255, 0.1)' : 'transparent'};
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        color: white;
        cursor: pointer;
        font-size: 13px;
        text-align: left;
        transition: all 0.2s;
      `;

      btn.addEventListener('click', () => setOverlay(overlay.id));
      btn.addEventListener('mouseenter', () => {
        if (state.currentOverlay !== overlay.id) {
          btn.style.background = 'rgba(255, 255, 255, 0.05)';
        }
      });
      btn.addEventListener('mouseleave', () => {
        if (state.currentOverlay !== overlay.id) {
          btn.style.background = 'transparent';
        }
      });

      menu.appendChild(btn);
    });

    return menu;
  }

  /**
   * Change l'overlay actif
   */
  function setOverlay(overlayId) {
    console.log(`[BotOverlay] Changement vers: ${overlayId}`);
    
    state.currentOverlay = overlayId;
    
    // Mettre à jour l'apparence des boutons
    document.querySelectorAll('[data-overlay]').forEach(btn => {
      const isActive = btn.dataset.overlay === overlayId;
      btn.style.background = isActive 
        ? 'rgba(255, 255, 255, 0.15)' 
        : 'transparent';
      btn.style.borderColor = isActive
        ? 'rgba(255, 255, 255, 0.4)'
        : 'rgba(255, 255, 255, 0.2)';
    });

    // Rafraîchir l'affichage
    render();
  }

  /**
   * Met à jour les données d'un overlay
   */
  function updateData(overlayType, data) {
    state.data[overlayType] = data;
    
    // Rafraîchir si c'est l'overlay actif
    if (state.currentOverlay === overlayType) {
      render();
    }
  }

  /**
   * Synchronise la transformation de l'overlay avec le canvas
   */
  function syncTransform() {
    if (!state.anchorElement || !state.svgElement) return;

    const anchorStyle = window.getComputedStyle(state.anchorElement);
    const transform = anchorStyle.transform;
    const bounds = state.anchorElement.getBoundingClientRect();

    // Appliquer la transformation
    state.svgElement.style.transform = transform;
    state.svgElement.style.transformOrigin = 'top left';
    
    // Ajuster la position pour tenir compte du viewport offset
    state.svgElement.style.left = `${bounds.left}px`;
    state.svgElement.style.top = `${bounds.top}px`;
  }

  /**
   * Démarre la boucle de synchronisation
   */
  function startSyncLoop() {
    if (state.updateTimer) {
      clearInterval(state.updateTimer);
    }

    state.updateTimer = setInterval(() => {
      syncTransform();
    }, CONFIG.UPDATE_INTERVAL);
  }

  /**
   * Arrête la boucle de synchronisation
   */
  function stopSyncLoop() {
    if (state.updateTimer) {
      clearInterval(state.updateTimer);
      state.updateTimer = null;
    }
  }

  /**
   * Rendu de l'overlay actif
   */
  function render() {
    // Nettoyer tous les groupes
    ['zones', 'actions'].forEach(layer => {
      const group = document.getElementById(`overlay-${layer}`);
      if (group) {
        group.innerHTML = '';
      }
    });

    // Rendre selon l'overlay actif
    switch (state.currentOverlay) {
      case 'frontier':
        renderFrontier();
        break;
      case 'actions':
        renderActions();
        break;
      case 'status':
        renderStatus();
        break;
      case 'off':
      default:
        // Rien à afficher
        break;
    }
  }

  /**
   * Rendu de l'overlay Frontier
   */
  function renderFrontier() {
    const data = state.data.frontier;
    if (!data || !data.cells) return;

    const container = document.getElementById('overlay-zones');
    
    data.cells.forEach(cell => {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      
      // Calcul position écran
      const x = cell.col * CONFIG.CELL_SIZE;
      const y = cell.row * CONFIG.CELL_SIZE;
      
      // Couleur selon focus level
      const color = cell.focus_level === 'TO_PROCESS' 
        ? COLORS.TO_PROCESS 
        : COLORS.PROCESSED;
      
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', CONFIG.CELL_SIZE);
      rect.setAttribute('height', CONFIG.CELL_SIZE);
      rect.setAttribute('fill', color);
      rect.setAttribute('stroke', 'rgba(255, 165, 0, 0.8)');
      rect.setAttribute('stroke-width', '1');
      
      container.appendChild(rect);
    });
  }

  /**
   * Rendu de l'overlay Actions
   */
  function renderActions() {
    const data = state.data.actions;
    if (!data || !data.actions) return;

    const container = document.getElementById('overlay-actions');
    
    data.actions.forEach(action => {
      const x = action.col * CONFIG.CELL_SIZE + CONFIG.CELL_SIZE / 2;
      const y = action.row * CONFIG.CELL_SIZE + CONFIG.CELL_SIZE / 2;
      
      // Symbole selon type d'action
      switch (action.type) {
        case 'SAFE':
          drawCircle(container, x, y, 8, COLORS.SAFE);
          break;
        case 'FLAG':
          drawCross(container, x, y, 8, COLORS.FLAG);
          break;
        case 'GUESS':
          drawQuestionMark(container, x, y, COLORS.GUESS);
          break;
      }
    });
  }

  /**
   * Rendu de l'overlay Status (tous les statuts)
   */
  function renderStatus() {
    const data = state.data.status;
    if (!data || !data.cells) return;

    const container = document.getElementById('overlay-zones');
    
    data.cells.forEach(cell => {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      
      const x = cell.col * CONFIG.CELL_SIZE;
      const y = cell.row * CONFIG.CELL_SIZE;
      
      // Couleur selon statut
      const color = COLORS[cell.status] || 'rgba(128, 128, 128, 0.2)';
      
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', CONFIG.CELL_SIZE);
      rect.setAttribute('height', CONFIG.CELL_SIZE);
      rect.setAttribute('fill', color);
      rect.setAttribute('stroke', 'rgba(255, 255, 255, 0.3)');
      rect.setAttribute('stroke-width', '0.5');
      
      container.appendChild(rect);
    });
  }

  /**
   * Dessine un cercle (action SAFE)
   */
  function drawCircle(container, cx, cy, radius, color) {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', cx);
    circle.setAttribute('cy', cy);
    circle.setAttribute('r', radius);
    circle.setAttribute('fill', color);
    circle.setAttribute('stroke', 'white');
    circle.setAttribute('stroke-width', '2');
    container.appendChild(circle);
  }

  /**
   * Dessine une croix (action FLAG)
   */
  function drawCross(container, cx, cy, size, color) {
    const line1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line1.setAttribute('x1', cx - size);
    line1.setAttribute('y1', cy - size);
    line1.setAttribute('x2', cx + size);
    line1.setAttribute('y2', cy + size);
    line1.setAttribute('stroke', color);
    line1.setAttribute('stroke-width', '3');
    line1.setAttribute('stroke-linecap', 'round');
    
    const line2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line2.setAttribute('x1', cx + size);
    line2.setAttribute('y1', cy - size);
    line2.setAttribute('x2', cx - size);
    line2.setAttribute('y2', cy + size);
    line2.setAttribute('stroke', color);
    line2.setAttribute('stroke-width', '3');
    line2.setAttribute('stroke-linecap', 'round');
    
    container.appendChild(line1);
    container.appendChild(line2);
  }

  /**
   * Dessine un point d'interrogation (action GUESS)
   */
  function drawQuestionMark(container, cx, cy, color) {
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', cx);
    text.setAttribute('y', cy);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'central');
    text.setAttribute('fill', color);
    text.setAttribute('stroke', 'black');
    text.setAttribute('stroke-width', '1');
    text.setAttribute('font-size', '16');
    text.setAttribute('font-weight', 'bold');
    text.textContent = '?';
    container.appendChild(text);
  }

  /**
   * Détruit l'overlay UI
   */
  function destroy() {
    console.log('[BotOverlay] Destruction...');
    
    stopSyncLoop();
    
    if (state.overlayContainer) {
      state.overlayContainer.remove();
    }
    
    // Reset state
    Object.keys(state).forEach(key => {
      state[key] = null;
    });
    state.currentOverlay = 'off';
    state.data = { frontier: null, actions: null, status: null };
  }

  // Exposer l'API publique
  window.BotOverlay = {
    init,
    destroy,
    setOverlay,
    updateData,
    render,
    getState: () => ({ ...state, data: { ...state.data } }),
  };

  console.log('[BotOverlay] Module chargé');
})();
