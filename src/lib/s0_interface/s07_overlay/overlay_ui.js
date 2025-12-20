/**
 * Bot Overlay UI - Surcouche Temps Réel
 * 
 * Overlay fluide indexé sur #anchor avec menu de contrôle fixe.
 * API exposée via window.BotUI
 */

(function () {
  'use strict';

  // === CONFIGURATION ===
  const CONFIG = {
    CELL_SIZE: 24,
    CELL_BORDER: 1,
    STRIDE: 25, // CELL_SIZE + CELL_BORDER (doit matcher avec config.py)
    UPDATE_INTERVAL: 16, // ~60 FPS
    Z_INDEX_OVERLAY: 9998,
    Z_INDEX_MENU: 9999,
    Z_INDEX_TOAST: 10000,
  };

  // === COULEURS ===
  const COLORS = {
    // Solver Status (très transparent pour s'intégrer avec le fond)
    UNREVEALED: 'rgba(0, 0, 0, 0)',
    ACTIVE: 'rgba(8, 106, 218, 0.2)',
    FRONTIER: 'rgba(255, 251, 0, 0.15)',
    SOLVED: 'rgba(21, 214, 53, 0.10)',
    MINE: 'rgba(255, 0, 0, 0.4)',
    TO_VISUALIZE: 'rgba(0, 0, 0, 0,15)',

    // Actions
    SAFE: 'rgba(0, 255, 0, 0.9)',
    FLAG: 'rgba(255, 50, 50, 0.9)',
    GUESS: 'rgba(255, 255, 0, 0.9)',

    // Focus Levels
    TO_PROCESS: 'rgba(255, 165, 0, 0.5)',
    PROCESSED: 'rgba(255, 200, 100, 0.25)',
    TO_REDUCE: 'rgba(0, 150, 255, 0.5)',
    REDUCED: 'rgba(100, 180, 255, 0.25)',

    // UI
    MENU_BG: 'rgba(20, 20, 30, 0.95)',
    MENU_BORDER: 'rgba(100, 100, 120, 0.5)',
    BUTTON_ACTIVE: 'rgba(80, 120, 200, 0.8)',
    BUTTON_HOVER: 'rgba(60, 80, 120, 0.5)',
  };

  // === ÉTAT GLOBAL ===
  const state = {
    initialized: false,
    currentOverlay: 'off',
    botRunning: false,
    menuCollapsed: false,
    autoExploration: false,

    // Données overlay
    data: {
      status: null,    // Statuts des cellules (ACTIVE, FRONTIER, etc.)
      actions: null,   // Actions planifiées (SAFE, FLAG, GUESS)
      probabilities: null, // Probabilités CSP
    },

    // Éléments DOM
    anchorElement: null,
    container: null,
    canvas: null,
    ctx: null,
    menuElement: null,

    // Animation
    animationFrame: null,
    lastAnchorRect: null,
  };

  // === INITIALISATION ===
  function init() {
    if (state.initialized) {
      console.log('[BotUI] Déjà initialisé');
      return true;
    }

    console.log('[BotUI] Initialisation...');

    // Trouver l'anchor
    state.anchorElement = document.getElementById('anchor');
    if (!state.anchorElement) {
      console.error('[BotUI] #anchor introuvable');
      return false;
    }

    // Créer la structure UI
    createUIStructure();

    // Démarrer la boucle de rendu
    startRenderLoop();

    // Écouter les touches clavier
    setupKeyboardShortcuts();

    state.initialized = true;
    showToast('Bot UI activée', 'success');
    console.log('[BotUI] Initialisé avec succès');
    return true;
  }

  // === STRUCTURE UI ===
  function createUIStructure() {
    // Container principal (couvre tout l'écran, pointer-events: none)
    state.container = document.createElement('div');
    state.container.id = 'bot-ui-container';
    state.container.style.cssText = `
      position: fixed;
      top: 0; left: 0;
      width: 100vw; height: 100vh;
      pointer-events: none;
      z-index: ${CONFIG.Z_INDEX_OVERLAY};
      overflow: hidden;
    `;

    // Canvas pour l'overlay (full viewport)
    state.canvas = document.createElement('canvas');
    state.canvas.id = 'bot-ui-canvas';
    state.canvas.style.cssText = `
      position: absolute;
      top: 0; left: 0;
      pointer-events: none;
      image-rendering: pixelated;
    `;
    state.ctx = state.canvas.getContext('2d');
    state.container.appendChild(state.canvas);

    // Menu de contrôle (fixe, pointer-events: auto)
    state.menuElement = createMenu();
    state.container.appendChild(state.menuElement);

    // Toast container
    const toastContainer = document.createElement('div');
    toastContainer.id = 'bot-ui-toasts';
    toastContainer.style.cssText = `
      position: fixed;
      bottom: 20px; right: 20px;
      display: flex;
      flex-direction: column-reverse;
      gap: 8px;
      pointer-events: none;
      z-index: ${CONFIG.Z_INDEX_TOAST};
    `;
    state.container.appendChild(toastContainer);

    document.body.appendChild(state.container);
  }

  // === MENU DE CONTRÔLE ===
  function createMenu() {
    const menu = document.createElement('div');
    menu.id = 'bot-ui-menu';
    menu.style.cssText = `
      position: fixed;
      top: 50%; left: 15px;
      transform: translateY(-50%);
      background: #f0f0f0;
      border: 1px solid #ccc;
      border-radius: 10px;
      padding: 0;
      pointer-events: auto;
      z-index: ${CONFIG.Z_INDEX_MENU};
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: #000;
      min-width: 180px;
      box-shadow: -4px 4px 12px rgba(0, 0, 0, 0.15);
      overflow: hidden;
      transition: all 0.3s ease;
    `;

    // Header avec titre et bouton collapse
    const header = document.createElement('div');
    header.style.cssText = `
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 12px;
      background: #e8e8e8;
      border-bottom: 1px solid #ccc;
      cursor: pointer;
    `;
    header.innerHTML = `
      <span style="font-weight: 600; font-size: 13px;">🤖 Bot 1000mines</span>
      <span id="bot-ui-collapse" style="font-size: 10px; opacity: 0.6;">▼</span>
    `;
    header.onclick = () => toggleMenuCollapse();
    menu.appendChild(header);

    // Contenu du menu (collapsible)
    const content = document.createElement('div');
    content.id = 'bot-ui-menu-content';
    content.style.cssText = `padding: 8px;`;

    // Section: Bot Control
    content.appendChild(createSection('Contrôle Bot', [
      { id: 'bot-toggle', label: '▶ Start', shortcut: 'F5', action: () => toggleBot() },
      { id: 'bot-restart', label: '🔄 Restart Game', shortcut: 'F6', action: () => restartGame() },
    ]));

    // Checkbox: Auto-Exploration
    content.appendChild(createCheckbox('auto-exploration', '🔍 Auto-Exploration', false, (checked) => {
      state.autoExploration = checked;
      syncControlState();
    }));

    // Section: Overlays
    content.appendChild(createSection('Overlays', [
      { id: 'overlay-off', label: '○ Off', shortcut: '1', action: () => setOverlay('off'), active: true },
      { id: 'overlay-status', label: '◆ Status', shortcut: '2', action: () => setOverlay('status') },
      { id: 'overlay-actions', label: '▶ Actions', shortcut: '3', action: () => setOverlay('actions') },
      { id: 'overlay-proba', label: '% Probas', shortcut: '4', action: () => setOverlay('probabilities') },
    ]));

    // Section: Assistance (future)
    content.appendChild(createSection('Assistance', [
      { id: 'assist-hint', label: '💡 Hint', shortcut: 'H', action: () => showHint(), disabled: true },
      { id: 'assist-solve', label: '🎯 Auto-solve', shortcut: 'A', action: () => autoSolve(), disabled: true },
    ]));

    // Footer avec raccourcis
    const footer = document.createElement('div');
    footer.style.cssText = `
      padding: 8px 12px;
      background: rgba(0,0,0,0.2);
      border-top: 1px solid ${COLORS.MENU_BORDER};
      font-size: 10px;
      opacity: 0.6;
    `;
    footer.innerHTML = `<kbd>M</kbd> Toggle Menu | <kbd>1-4</kbd> Overlays`;
    content.appendChild(footer);

    menu.appendChild(content);
    return menu;
  }

  function createSection(title, buttons) {
    const section = document.createElement('div');
    section.style.cssText = `margin-bottom: 8px;`;

    const titleEl = document.createElement('div');
    titleEl.textContent = title;
    titleEl.style.cssText = `
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      opacity: 0.5;
      margin-bottom: 6px;
      padding-left: 4px;
    `;
    section.appendChild(titleEl);

    buttons.forEach(btn => {
      const button = document.createElement('button');
      button.id = btn.id;
      button.dataset.action = btn.id;
      button.innerHTML = `
        <span>${btn.label}</span>
        <kbd style="font-size: 9px; opacity: 0.5; background: rgba(255,255,255,0.1); padding: 2px 5px; border-radius: 3px;">${btn.shortcut}</kbd>
      `;
      button.style.cssText = `
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
        padding: 8px 10px;
        margin: 2px 0;
        background: ${btn.active ? COLORS.BUTTON_ACTIVE : 'transparent'};
        border: none;
        border-radius: 6px;
        color: ${btn.disabled ? 'rgba(0,0,0,0.3)' : '#000'};
        cursor: ${btn.disabled ? 'not-allowed' : 'pointer'};
        font-size: 12px;
        text-align: left;
        transition: all 0.15s ease;
        opacity: ${btn.disabled ? 0.5 : 1};
      `;

      if (!btn.disabled) {
        button.onmouseenter = () => {
          if (!button.classList.contains('active')) {
            button.style.background = COLORS.BUTTON_HOVER;
          }
        };
        button.onmouseleave = () => {
          if (!button.classList.contains('active')) {
            button.style.background = 'transparent';
          }
        };
        button.onclick = btn.action;
      }

      if (btn.active) button.classList.add('active');
      section.appendChild(button);
    });

    return section;
  }

  function createCheckbox(id, label, defaultChecked, onChange) {
    const container = document.createElement('div');
    container.style.cssText = `
      display: flex;
      align-items: center;
      padding: 8px 10px;
      margin: 4px 0;
      background: rgba(0,0,0,0.05);
      border-radius: 6px;
      cursor: pointer;
      user-select: none;
    `;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = id;
    checkbox.checked = defaultChecked;
    checkbox.style.cssText = `
      width: 16px;
      height: 16px;
      margin-right: 8px;
      cursor: pointer;
    `;

    const labelEl = document.createElement('label');
    labelEl.htmlFor = id;
    labelEl.textContent = label;
    labelEl.style.cssText = `
      font-size: 12px;
      cursor: pointer;
      flex: 1;
    `;

    checkbox.addEventListener('change', () => onChange(checkbox.checked));
    container.onclick = () => {
      checkbox.checked = !checkbox.checked;
      onChange(checkbox.checked);
    };

    container.appendChild(checkbox);
    container.appendChild(labelEl);
    return container;
  }


  function toggleMenuCollapse() {
    state.menuCollapsed = !state.menuCollapsed;
    const content = document.getElementById('bot-ui-menu-content');
    const collapse = document.getElementById('bot-ui-collapse');

    if (state.menuCollapsed) {
      content.style.display = 'none';
      collapse.textContent = '▶';
    } else {
      content.style.display = 'block';
      collapse.textContent = '▼';
    }
  }

  // === OVERLAYS ===
  function setOverlay(overlayId) {
    console.log(`[BotUI] Overlay: ${overlayId}`);
    state.currentOverlay = overlayId;

    // Mettre à jour les boutons
    document.querySelectorAll('[id^="overlay-"]').forEach(btn => {
      const isActive = btn.id === `overlay-${overlayId}`;
      btn.style.background = isActive ? COLORS.BUTTON_ACTIVE : 'transparent';
      btn.classList.toggle('active', isActive);
    });

    render();
  }

  function updateData(type, data) {
    state.data[type] = data;
    if (state.currentOverlay === type) {
      render();
    }
  }

  // === RENDU ===
  function startRenderLoop() {
    function loop() {
      syncWithAnchor();
      state.animationFrame = requestAnimationFrame(loop);
    }
    loop();
  }

  function stopRenderLoop() {
    if (state.animationFrame) {
      cancelAnimationFrame(state.animationFrame);
      state.animationFrame = null;
    }
  }

  function syncWithAnchor() {
    console.log('[BotUI] syncWithAnchor called');

    if (!state.anchorElement || !state.canvas) {
      console.log('[BotUI] syncWithAnchor early return - anchor:', !!state.anchorElement, 'canvas:', !!state.canvas);
      return;
    }

    const rect = state.anchorElement.getBoundingClientRect();

    // Chercher l'élément controller pour les dimensions (id="control")
    const controller = document.getElementById('control');

    if (!controller) {
      console.error('[BotUI] Controller #control non trouvé!');
      return;
    }

    const controllerRect = controller.getBoundingClientRect();
    console.log(`[BotUI] Controller trouvé: ${controller.tagName}#${controller.id}, taille: ${controllerRect.width}x${controllerRect.height}`);

    // Vérifier si la position a changé
    const changed = !state.lastAnchorRect ||
      rect.left !== state.lastAnchorRect.left ||
      rect.top !== state.lastAnchorRect.top ||
      rect.width !== state.lastAnchorRect.width ||
      rect.height !== state.lastAnchorRect.height ||
      controllerRect.width !== state.lastControllerRect?.width ||
      controllerRect.height !== state.lastControllerRect?.height;

    if (changed || !state.lastControllerRect) {  // Forcer la première fois
      state.lastAnchorRect = { ...rect };
      state.lastControllerRect = { ...controllerRect };

      // FORCER les dimensions du canvas selon controller
      const newWidth = Math.round(controllerRect.width);
      const newHeight = Math.round(controllerRect.height);

      console.log(`[BotUI] Mise à jour canvas: ${state.canvas.width}x${state.canvas.height} -> ${newWidth}x${newHeight}`);

      // IMPORTANT: Canvas interne = taille du controller
      state.canvas.width = newWidth;
      state.canvas.height = newHeight;

      // CSS: taille identique (pas de transformation)
      state.canvas.style.width = `${newWidth}px`;
      state.canvas.style.height = `${newHeight}px`;

      // Positionner le canvas exactement sur le controller
      state.canvas.style.left = `${Math.round(controllerRect.left)}px`;
      state.canvas.style.top = `${Math.round(controllerRect.top)}px`;

      // Calculer le STRIDE réel dynamiquement basé sur l'anchor
      const realStride = rect.width / 24; // STRIDE = CELL_SIZE + CELL_BORDER

      // Mettre à jour CONFIG avec les valeurs réelles
      CONFIG.REAL_STRIDE = realStride;
      CONFIG.REAL_CELL_SIZE = 24;

      // Stocker l'offset de l'anchor pour le dessin
      CONFIG.ANCHOR_OFFSET_X = rect.left - controllerRect.left;
      CONFIG.ANCHOR_OFFSET_Y = rect.top - controllerRect.top;

      console.log(`[BotUI] Canvas: ${state.canvas.width}x${state.canvas.height}`);
      console.log(`[BotUI] Anchor offset: (${CONFIG.ANCHOR_OFFSET_X}, ${CONFIG.ANCHOR_OFFSET_Y})`);
      console.log(`[BotUI] Cellules réelles: stride=${realStride.toFixed(2)}px, cell=${CONFIG.REAL_CELL_SIZE}px`);

      render(); // Re-render après resize
    }
  }

  function render() {
    if (!state.ctx || !state.canvas.width) return;

    // Clear
    state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);

    // Render selon l'overlay actif
    switch (state.currentOverlay) {
      case 'status':
        renderStatus();
        break;
      case 'actions':
        renderActions();
        break;
      case 'probabilities':
        renderProbabilities();
        break;
      case 'off':
      default:
        break;
    }
  }

  function renderStatus() {
    const data = state.data.status;
    if (!data || !data.cells) return;

    const ctx = state.ctx;

    data.cells.forEach(cell => {
      // Utiliser le STRIDE réel calculé dynamiquement
      const stride = CONFIG.REAL_STRIDE || CONFIG.STRIDE;
      const cellSize = CONFIG.REAL_CELL_SIZE || CONFIG.CELL_SIZE;

      // Calculer position avec offset de l'anchor
      const x = cell.col * stride + CONFIG.ANCHOR_OFFSET_X;
      const y = cell.row * stride + CONFIG.ANCHOR_OFFSET_Y;

      // Skip si hors du viewport
      if (x + stride < 0 || y + stride < 0 ||
        x > state.canvas.width || y > state.canvas.height) {
        return;
      }

      // Couleur selon le statut ou le focus level
      if (cell.status === 'UNREVEALED') return;
      let color = COLORS[cell.focus_level] || COLORS[cell.status] || 'rgba(128,128,128,0.1)';

      ctx.fillStyle = color;
      ctx.fillRect(x, y, cellSize, cellSize);

      // Dessiner uniquement la bordure droite et bas (rectangles 1px, sans débordement)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.01)';
      // Bordure droite : x + cellSize (24) sur hauteur stride (25)
      ctx.fillRect(x + cellSize, y, 1, stride);
      // Bordure bas : y + cellSize (24) sur largeur stride (25)
      ctx.fillRect(x, y + cellSize, stride, 1);
    });
  }

  function renderActions() {
    const data = state.data.actions;
    if (!data || !data.actions) return;

    const ctx = state.ctx;

    data.actions.forEach(action => {
      // Utiliser le STRIDE réel calculé dynamiquement
      const stride = CONFIG.REAL_STRIDE || CONFIG.STRIDE;
      const cellSize = CONFIG.REAL_CELL_SIZE || CONFIG.CELL_SIZE;

      // Calculer position avec offset de l'anchor
      const cx = action.col * stride + cellSize / 2 + CONFIG.ANCHOR_OFFSET_X;
      const cy = action.row * stride + cellSize / 2 + CONFIG.ANCHOR_OFFSET_Y;

      // Skip si hors du viewport (avec marge pour les formes)
      if (cx + 20 < 0 || cy + 20 < 0 ||
        cx - 20 > state.canvas.width || cy - 20 > state.canvas.height) {
        return;
      }

      ctx.save();

      switch (action.type) {
        case 'SAFE':
          ctx.beginPath();
          ctx.arc(cx, cy, 8, 0, Math.PI * 2);
          ctx.fillStyle = COLORS.SAFE;
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.stroke();
          break;

        case 'FLAG':
          ctx.strokeStyle = COLORS.FLAG;
          ctx.lineWidth = 3;
          ctx.lineCap = 'round';
          ctx.beginPath();
          ctx.moveTo(cx - 6, cy - 6);
          ctx.lineTo(cx + 6, cy + 6);
          ctx.moveTo(cx + 6, cy - 6);
          ctx.lineTo(cx - 6, cy + 6);
          ctx.stroke();
          break;

        case 'GUESS':
          ctx.font = 'bold 14px sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = COLORS.GUESS;
          ctx.strokeStyle = '#000';
          ctx.lineWidth = 2;
          ctx.strokeText('?', cx, cy);
          ctx.fillText('?', cx, cy);
          break;
      }

      ctx.restore();
    });
  }

  function renderProbabilities() {
    const data = state.data.probabilities;
    if (!data || !data.cells) return;

    const ctx = state.ctx;

    data.cells.forEach(cell => {
      // Utiliser le STRIDE réel calculé dynamiquement
      const stride = CONFIG.REAL_STRIDE || CONFIG.STRIDE;
      const cellSize = CONFIG.REAL_CELL_SIZE || CONFIG.CELL_SIZE;

      // Calculer position avec offset de l'anchor
      const x = cell.col * stride + CONFIG.ANCHOR_OFFSET_X;
      const y = cell.row * stride + CONFIG.ANCHOR_OFFSET_Y;

      // Skip si hors du viewport
      if (x + stride < 0 || y + stride < 0 ||
        x > state.canvas.width || y > state.canvas.height) {
        return;
      }

      const prob = cell.probability;

      // Gradient rouge (100% mine) -> vert (0% mine)
      const r = Math.round(255 * prob);
      const g = Math.round(255 * (1 - prob));
      const color = `rgba(${r}, ${g}, 0, 0.6)`;

      ctx.fillStyle = color;
      ctx.fillRect(x, y, cellSize, cellSize);

      // Afficher le % si > 0 et < 100
      if (prob > 0.01 && prob < 0.99) {
        ctx.font = 'bold 9px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#fff';
        ctx.fillText(`${Math.round(prob * 100)}`, x + cellSize / 2, y + cellSize / 2);
      }
    });
  }

  // === BOT CONTROL ===
  function toggleBot() {
    state.botRunning = !state.botRunning;
    updateBotButtons();

    const message = state.botRunning ? 'Bot démarré' : 'Bot en pause';
    const type = state.botRunning ? 'success' : 'warning';
    showToast(message, type);

    // Émettre un événement custom pour Python
    const event = state.botRunning ? 'botui:start' : 'botui:pause';
    window.dispatchEvent(new CustomEvent(event));
  }

  function restartGame() {
    showToast('Redémarrage de la partie...', 'info');

    // Flag pour que Python puisse le détecter
    window.__botui_restart_requested = true;
    window.__botui_auto_restart = true;  // Indique qu'il faut auto-relancer comme 'y'

    // Émettre un événement custom pour Python
    window.dispatchEvent(new CustomEvent('botui:restart'));
  }

  function updateBotButtons() {
    const toggleBtn = document.getElementById('bot-toggle');

    if (toggleBtn) {
      const label = state.botRunning ? '⏸ Pause' : '▶ Start';
      const span = toggleBtn.querySelector('span:first-child');
      if (span) span.textContent = label;

      toggleBtn.style.background = state.botRunning ? COLORS.BUTTON_ACTIVE : 'transparent';
    }
  }

  // === ASSISTANCE (FUTURE) ===
  function showHint() {
    showToast('Hint: Non implémenté', 'info');
  }

  function autoSolve() {
    showToast('Auto-solve: Non implémenté', 'info');
  }

  // === RACCOURCIS CLAVIER ===
  function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Ignorer si focus sur un input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case 'F5':
          e.preventDefault();
          toggleBot();
          break;
        case 'F6':
          e.preventDefault();
          restartGame();
          break;
        case '1':
          setOverlay('off');
          break;
        case '2':
          setOverlay('status');
          break;
        case '3':
          setOverlay('actions');
          break;
        case '4':
          setOverlay('probabilities');
          break;
        case 'm':
        case 'M':
          toggleMenuCollapse();
          break;
        case 'h':
        case 'H':
          showHint();
          break;
      }
    });
  }

  // === TOASTS ===
  function showToast(message, type = 'info') {
    const container = document.getElementById('bot-ui-toasts');
    if (!container) return;

    const colors = {
      success: '#4CAF50',
      warning: '#FF9800',
      error: '#f44336',
      info: '#2196F3',
    };

    const toast = document.createElement('div');
    toast.style.cssText = `
      background: ${colors[type] || colors.info};
      color: white;
      padding: 10px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-family: 'Segoe UI', sans-serif;
      box-shadow: 0 3px 10px rgba(0,0,0,0.3);
      animation: slideIn 0.3s ease;
      pointer-events: auto;
    `;
    toast.textContent = message;

    // Animation CSS
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
      @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
      }
    `;
    document.head.appendChild(style);

    container.appendChild(toast);

    // Auto-remove après 3s
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // === DESTRUCTION ===
  function destroy() {
    console.log('[BotUI] Destruction...');

    stopRenderLoop();

    if (state.container) {
      state.container.remove();
    }

    state.initialized = false;
    state.container = null;
    state.canvas = null;
    state.ctx = null;
    state.menuElement = null;
    state.data = { status: null, actions: null, probabilities: null };
  }

  // === CONTROL STATE ===
  function getControlState() {
    return {
      botRunning: state.botRunning,
      autoExploration: state.autoExploration,
    };
  }

  function syncControlState() {
    // Called when control state changes - Python reads via getControlState()
    console.log('[BotUI] Control state synced:', getControlState());
  }


  // === API PUBLIQUE ===
  window.BotUI = {
    init,
    destroy,
    setOverlay,
    updateData,
    render,
    toggleBot,
    restartGame,
    showToast,
    getState: () => ({ ...state }),
    isRunning: () => state.botRunning,
    getControlState,
  };

  console.log('[BotUI] Module chargé - Appeler BotUI.init() pour activer');
})();
