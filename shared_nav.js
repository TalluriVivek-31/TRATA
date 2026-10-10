/**
 * CYCLONEX — Multi-Page Navigation & Global State Manager
 * Shared Header, Responsive Mobile Drawer, Storm Selector Sync & Live Health Telemetry
 */

(function() {
  'use strict';

  const dataset = window.CYCLONEX_DATASET || {};
  const initialKey = localStorage.getItem('cyclonex_active_storm') || 'REMAL_2024';

  // Global CYCLONEX Shared State
  window.CYCLONEX = window.CYCLONEX || {
    selectedStormKey: initialKey,
    selectedStormData: dataset[initialKey] || (Object.keys(dataset).length > 0 ? dataset[Object.keys(dataset)[0]] : null),
    apiBase: window.location.protocol.startsWith('http') ? '' : 'http://127.0.0.1:8000'
  };

  // Client-Side Session Auth Guard
  // Accurately recognizes both clean URLs (/login, /) and static file URLs (/login.html, index.html)
  const currentPath = window.location.pathname.toLowerCase();
  const rawFile = currentPath.split('/').pop() || 'index.html';
  const currentBase = rawFile.replace(/\.html$/, '');
  const isLoginPage = currentBase === 'login' || currentPath === '/login' || currentPath.endsWith('/login');
  const rawUser = sessionStorage.getItem('cyclonex_user');
  let authUser = null;
  try {
    if (rawUser) authUser = JSON.parse(rawUser);
  } catch (e) {
    sessionStorage.removeItem('cyclonex_user');
  }

  // Determine appropriate target format (clean URLs on Vercel vs .html on file/standalone)
  const isCleanUrlMode = !window.location.pathname.endsWith('.html') && window.location.protocol !== 'file:';
  const loginTarget = isCleanUrlMode ? 'login' : 'login.html';
  const homeTarget = isCleanUrlMode ? '/' : 'index.html';

  if (!authUser && !isLoginPage) {
    // Preserve intended destination URL (strictly exclude login itself to avoid loops)
    const destination = window.location.href;
    if (!destination.includes('/login') && !destination.includes('login.html')) {
      sessionStorage.setItem('cyclonex_redirect', destination);
    }
    window.location.replace(loginTarget);
    return;
  } else if (authUser && isLoginPage) {
    // If authenticated user visits login, direct to preserved destination or overview dashboard
    const savedRedirect = sessionStorage.getItem('cyclonex_redirect');
    sessionStorage.removeItem('cyclonex_redirect');
    const isLoginDest = savedRedirect && (savedRedirect.includes('/login') || savedRedirect.includes('login.html'));
    window.location.replace((savedRedirect && !isLoginDest) ? savedRedirect : homeTarget);
    return;
  }

  // 8 Primary Operational Navigation Modules (Portal Login strictly excluded from nav bar)
  const PAGES = [
    { title: 'Overview', path: 'index.html', href: 'index.html' },
    { title: 'Detection', path: 'detection.html', href: 'detection.html' },
    { title: 'Classification', path: 'classification.html', href: 'classification.html' },
    { title: 'Track', path: 'track.html', href: 'track.html', fullTitle: 'Track & Forecast' },
    { title: 'Intensity', path: 'intensity.html', href: 'intensity.html' },
    { title: 'Explorer', path: 'data-explorer.html', href: 'data-explorer.html', fullTitle: 'Data Explorer' },
    { title: 'Model Lab', path: 'model-lab.html', href: 'model-lab.html' },
    { title: 'System', path: 'system.html', href: 'system.html' }
  ];

  function renderSharedHeader() {
    const headerContainer = document.getElementById('cyclonexSharedHeader');
    if (!headerContainer) return;

    // Desktop nav shows primary operational modules
    const desktopLinksHtml = PAGES.map(p => {
      const pBase = p.path.replace(/\.html$/, '');
      const isActive = currentBase === pBase || (currentBase === '' && pBase === 'index') || (currentBase === 'index' && pBase === 'index');
      return `<a href="${p.href}" class="nav-pill-link ${isActive ? 'active' : ''}">${p.title}</a>`;
    }).join('');

    // Drawer shows all links with full descriptive titles
    const drawerLinksHtml = PAGES.map(p => {
      const pBase = p.path.replace(/\.html$/, '');
      const isActive = currentBase === pBase || (currentBase === '' && pBase === 'index') || (currentBase === 'index' && pBase === 'index');
      return `<a href="${p.href}" class="nav-pill-link ${isActive ? 'active' : ''}">${p.fullTitle || p.title}</a>`;
    }).join('');

    const isLoggedIn = !!authUser;
    const operatorName = (authUser && (authUser.operator_name || authUser.employee_id)) || 'Officer (MET-26070)';
    const clearance = (authUser && authUser.clearance_level) || 'LEVEL-IV SCIENTIFIC';

    headerContainer.innerHTML = `
      <header class="cyclonex-header-bar" role="banner">
        <div class="header-left">
          <a href="index.html" class="header-brand-logo" aria-label="CYCLONEX Homepage">
            <span class="brand-dash">—</span> CYCLONEX
          </a>
          <span class="header-sih-tag">SIH 26070</span>
        </div>

        <nav class="header-nav-scroll-pill" role="navigation" aria-label="Main Navigation">
          ${desktopLinksHtml}
        </nav>

        <div class="header-right-controls">
          <div class="global-storm-dropdown-wrap">
            <label for="globalStormSelect" class="sr-only">Active Cyclone</label>
            <select id="globalStormSelect" class="global-storm-select" aria-label="Select Cyclone Dataset">
              <!-- Dynamically populated -->
            </select>
          </div>
          
          <div class="system-status-indicator" id="headerStatusBadge" title="Backend API Health">
            <span class="status-pulse-dot" id="headerStatusDot"></span>
            <span class="status-text" id="headerStatusText">SYNCING</span>
          </div>

          <!-- Profile / Operator Avatar Dropdown Component -->
          <div class="header-profile-wrap" id="headerProfileWrap">
            <button 
              id="headerProfileBtn" 
              class="header-profile-btn ${isLoggedIn ? 'authenticated' : ''}" 
              aria-label="User Profile & Authentication Menu" 
              aria-haspopup="true" 
              aria-expanded="false"
              title="${isLoggedIn ? operatorName : 'Operator Authentication'}"
            >
              <svg class="profile-avatar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              ${isLoggedIn ? '<span class="profile-active-indicator" title="Active Session"></span>' : ''}
            </button>

            <div id="profileDropdownMenu" class="profile-dropdown-menu" role="menu" aria-hidden="true">
              ${isLoggedIn ? `
                <div class="profile-user-info">
                  <div class="profile-badge-label">AUTHENTICATED OPERATOR</div>
                  <div class="profile-user-name">${operatorName}</div>
                  <div class="profile-user-clearance">${clearance}</div>
                </div>
                <div class="profile-menu-divider"></div>
                <button type="button" id="btnProfileSignOut" class="profile-menu-item danger" role="menuitem">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                  </svg>
                  <span>Sign out</span>
                </button>
              ` : `
                <div class="profile-user-info">
                  <div class="profile-badge-label">AUTHENTICATION STATUS</div>
                  <div class="profile-user-name">Signed Out</div>
                  <div class="profile-user-clearance">Meteorological Clearance Required</div>
                </div>
                <div class="profile-menu-divider"></div>
                <a href="${loginTarget}" id="btnProfileSignIn" class="profile-menu-item primary" role="menuitem">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
                    <polyline points="10 17 15 12 10 7"></polyline>
                    <line x1="15" y1="12" x2="3" y2="12"></line>
                  </svg>
                  <span>Sign in</span>
                </a>
              `}
            </div>
          </div>

          <!-- Mobile Hamburger Toggle -->
          <button id="mobileNavToggle" class="mobile-nav-toggle" aria-label="Open Navigation Menu" aria-expanded="false">
            <span></span>
            <span></span>
            <span></span>
          </button>
        </div>
      </header>

      <!-- Responsive Mobile Drawer Navigation -->
      <div id="mobileNavDrawer" class="mobile-nav-drawer" aria-hidden="true">
        <div class="mobile-nav-header">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="header-brand-logo" style="font-size:1.3rem;"><span class="brand-dash">—</span> CYCLONEX</span>
          </div>
          <button id="mobileNavClose" class="mobile-nav-close" aria-label="Close navigation menu">&times;</button>
        </div>

        <div class="mobile-nav-links">
          ${drawerLinksHtml}
        </div>


        <div class="mobile-nav-footer">
          <div style="display:flex; flex-direction:column; gap:0.4rem;">
            <label for="globalStormSelectMobile" class="utility-label utility-label--accent">SELECT ACTIVE CYCLONE</label>
            <select id="globalStormSelectMobile" class="global-storm-select mobile" aria-label="Select Cyclone Dataset Mobile">
              <!-- Dynamically populated -->
            </select>
          </div>
          <div class="system-status-indicator" style="justify-content:center;">
            <span class="status-pulse-dot" id="mobileStatusDot"></span>
            <span class="status-text" id="mobileStatusText">SYNCING</span>
          </div>
        </div>
      </div>
      <div id="mobileNavBackdrop" class="mobile-nav-backdrop"></div>
    `;

    initGlobalStormSelects();
    initMobileDrawer();
    initProfileDropdown();
    checkBackendHealth();
  }

  function initProfileDropdown() {
    const wrap = document.getElementById('headerProfileWrap');
    const btn = document.getElementById('headerProfileBtn');
    const menu = document.getElementById('profileDropdownMenu');
    const btnSignOut = document.getElementById('btnProfileSignOut');

    if (!btn || !menu) return;

    function openMenu() {
      menu.classList.add('open');
      menu.setAttribute('aria-hidden', 'false');
      btn.setAttribute('aria-expanded', 'true');
    }

    function closeMenu() {
      menu.classList.remove('open');
      menu.setAttribute('aria-hidden', 'true');
      btn.setAttribute('aria-expanded', 'false');
    }

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains('open');
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
      if (!wrap || !wrap.contains(e.target)) {
        closeMenu();
      }
    });

    // Close on Escape key
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && menu.classList.contains('open')) {
        closeMenu();
        btn.focus();
      }
    });

    // Handle Sign out
    if (btnSignOut) {
      btnSignOut.addEventListener('click', async () => {
        if (window.CYCLONEX_FIREBASE) {
          try {
            if (window.CYCLONEX_FIREBASE.trackEvent) {
              window.CYCLONEX_FIREBASE.trackEvent('sign_out');
            }
            if (window.CYCLONEX_FIREBASE.signOutOperator) {
              await window.CYCLONEX_FIREBASE.signOutOperator();
            }
          } catch (e) {}
        }
        sessionStorage.removeItem('cyclonex_user');
        sessionStorage.removeItem('cyclonex_redirect');
        window.location.replace(loginTarget);
      });
    }
  }

  // Load Firebase Config Module dynamically if not yet imported
  if (!window.CYCLONEX_FIREBASE) {
    import('./firebase_config.js').catch(err => {
      // Non-blocking in case module loading is deferred
    });
  }

  function initGlobalStormSelects() {
    const desktopSel = document.getElementById('globalStormSelect');
    const mobileSel = document.getElementById('globalStormSelectMobile');
    const selects = [desktopSel, mobileSel].filter(Boolean);

    if (selects.length === 0) return;

    selects.forEach(sel => {
      sel.innerHTML = '';

      const optLive = document.createElement('option');
      optLive.value = 'LIVE_SURVEILLANCE';
      optLive.textContent = '🛰️ REAL-TIME LIVE BASIN SURVEILLANCE';
      sel.appendChild(optLive);

      const grpIndian = document.createElement('optgroup');
      grpIndian.label = 'RSMC NEW DELHI / IMD BEST TRACKS';
      const grpPacific = document.createElement('optgroup');
      grpPacific.label = 'CMA BEST-TRACK ARCHIVE';

      Object.keys(dataset).forEach(k => {
        const s = dataset[k];
        const opt = document.createElement('option');
        opt.value = k;
        opt.textContent = `${s.name} (${s.year})`;

        if (k.startsWith('REMAL') || k.startsWith('DANA') || k.startsWith('BIPARJOY') || k.startsWith('AMPHAN')) {
          grpIndian.appendChild(opt);
        } else {
          grpPacific.appendChild(opt);
        }
      });

      sel.appendChild(grpIndian);
      sel.appendChild(grpPacific);

      // Set initial value
      const currentStoredKey = window.CYCLONEX.selectedStormKey;
      if (currentStoredKey === 'LIVE_SURVEILLANCE') {
        sel.value = 'LIVE_SURVEILLANCE';
        window.CYCLONEX.selectedStormData = null;
      } else if (dataset[currentStoredKey]) {
        sel.value = currentStoredKey;
        window.CYCLONEX.selectedStormData = dataset[currentStoredKey];
      } else {
        sel.value = 'AMPHAN_2020';
        window.CYCLONEX.selectedStormKey = sel.value;
        window.CYCLONEX.selectedStormData = dataset[sel.value];
      }

      sel.addEventListener('change', (e) => {
        const newKey = e.target.value;
        window.CYCLONEX.selectedStormKey = newKey;
        window.CYCLONEX.selectedStormData = dataset[newKey] || null;
        localStorage.setItem('cyclonex_active_storm', newKey);

        // Keep both selects in sync
        selects.forEach(otherSel => {
          if (otherSel !== sel) otherSel.value = newKey;
        });

        // Dispatch custom event for reactive page re-renders
        window.dispatchEvent(new CustomEvent('cyclonex:stormChanged', {
          detail: { key: newKey, storm: window.CYCLONEX.selectedStormData, isLive: (newKey === 'LIVE_SURVEILLANCE') }
        }));
      });
    });
  }

  function initMobileDrawer() {
    const toggleBtn = document.getElementById('mobileNavToggle');
    const closeBtn = document.getElementById('mobileNavClose');
    const drawer = document.getElementById('mobileNavDrawer');
    const backdrop = document.getElementById('mobileNavBackdrop');

    if (!toggleBtn || !drawer || !backdrop) return;

    function openDrawer() {
      drawer.classList.add('open');
      backdrop.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
      toggleBtn.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
    }

    function closeDrawer() {
      drawer.classList.remove('open');
      backdrop.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
      toggleBtn.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    }

    toggleBtn.addEventListener('click', openDrawer);
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    backdrop.addEventListener('click', closeDrawer);

    // Close on Escape key
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && drawer.classList.contains('open')) {
        closeDrawer();
      }
    });

    // Close drawer when a link is clicked
    drawer.querySelectorAll('.nav-pill-link').forEach(link => {
      link.addEventListener('click', closeDrawer);
    });
  }

  async function checkBackendHealth() {
    const statusText = document.getElementById('headerStatusText');
    const statusDot = document.getElementById('headerStatusDot');
    const mobileText = document.getElementById('mobileStatusText');
    const mobileDot = document.getElementById('mobileStatusDot');

    const apiBase = window.CYCLONEX.apiBase;

    try {
      let data = window.CYCLONEX && window.CYCLONEX.health;
      if (!data) {
        const res = await fetch(`${apiBase}/api/health`);
        if (res.ok) {
          data = await res.json();
          if (window.CYCLONEX) window.CYCLONEX.health = data;
        }
      }
      if (data && (data.status === 'OK' || data.status === 'healthy')) {
        if (statusText) statusText.textContent = 'ONLINE';
        if (mobileText) mobileText.textContent = 'ONLINE';
        if (statusDot) {
          statusDot.style.background = '#65BDD1';
          statusDot.style.boxShadow = '0 0 8px #65BDD1';
        }
        if (mobileDot) {
          mobileDot.style.background = '#65BDD1';
          mobileDot.style.boxShadow = '0 0 8px #65BDD1';
        }
        return;
      }
      throw new Error('Non-OK health response');
    } catch {
      if (statusText) statusText.textContent = 'LOCAL/STANDALONE';
      if (mobileText) mobileText.textContent = 'LOCAL/STANDALONE';
      if (statusDot) {
        statusDot.style.background = '#f59e0b';
        statusDot.style.boxShadow = '0 0 8px #f59e0b';
      }
      if (mobileDot) {
        mobileDot.style.background = '#f59e0b';
        mobileDot.style.boxShadow = '0 0 8px #f59e0b';
      }
    }
  }

  // Render when DOM is loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderSharedHeader);
  } else {
    renderSharedHeader();
  }

})();
