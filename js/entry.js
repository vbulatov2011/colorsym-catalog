/* entry.js — Interactive behavior shared by every color-group entry page:
 * - Partition table layer toggles & presets with deferred data-src hydration
 * - Panel backdrop switcher (white / checker / dark) for pale palettes
 * - Inline interactive SymmHub preview drawer + Sync overlays toggle
 * - Live SymmHub deep links (Explore ?ui=simple + Edit in Studio) per coloring
 * - Click-to-copy math/permutation buttons
 * - Interactive row/column & representative-column hover highlighting
 * - Lightbox with 2D grid navigation, on-screen arrows, live layer toggles & live link
 * - Prev / Next color group keyboard shortcuts ([ and ]) */
(function () {
  var LAYER_KEY = 'colorsym-catalog.entry.layers';
  var BG_KEY = 'colorsym-catalog.entry.backdrop';
  var SYNC_OV_KEY = 'colorsym-catalog.live.syncOverlays';
  var PRESETS = {
    clean:   { pat: true,  ghost: true,  gfd: false, hfd: false, gtil: false, htil: false, gsym: false, hsym: false, g: false, f: false },
    domains: { pat: true,  ghost: true,  gfd: true,  hfd: true,  gtil: true,  htil: true,  gsym: false, hsym: false, g: true,  f: true  },
    syms:    { pat: true,  ghost: false, gfd: false, hfd: true,  gtil: false, htil: false, gsym: true,  hsym: true,  g: false, f: false },
    all:     { pat: true,  ghost: true,  gfd: true,  hfd: true,  gtil: true,  htil: true,  gsym: true,  hsym: true,  g: true,  f: true  },
  };
  var KEY_TO_CLASS = {
    pat: 'pat', ghost: 'ghost', gfd: 'gfd', hfd: 'hfd',
    gtil: 'gtil', htil: 'htil', gsym: 'gsym', hsym: 'hsym',
    f: 'fglyph', g: 'gglyph',
  };

  // ---- Layer state & controls ----------------------------------------------
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(LAYER_KEY)) || {}; } catch (e) {}

  var allBoxes = [].slice.call(document.querySelectorAll('input[data-k]'));
  var layerState = {};

  allBoxes.forEach(function (cb) {
    var k = cb.getAttribute('data-k');
    if (layerState[k] === undefined) {
      layerState[k] = typeof saved[k] === 'boolean' ? saved[k] : cb.checked;
    }
  });

  var syncOverlays = false;
  try { syncOverlays = localStorage.getItem(SYNC_OV_KEY) === '1'; } catch (e) {}

  function hydrateLayer(k) {
    var cls = KEY_TO_CLASS[k];
    if (!cls) return;
    document.querySelectorAll('img.' + cls + '[data-src]').forEach(function (img) {
      img.src = img.getAttribute('data-src');
      img.removeAttribute('data-src');
    });
  }

  // Forward declarations populated below
  var refreshAllLiveLinks = function () {};
  var refreshLiveDrawer = function () {};

  function syncLayers() {
    Object.keys(layerState).forEach(function (k) {
      document.body.classList.toggle('off-' + k, !layerState[k]);
      if (layerState[k]) hydrateLayer(k);
    });
    allBoxes.forEach(function (cb) {
      var k = cb.getAttribute('data-k');
      if (k in layerState) cb.checked = layerState[k];
    });
    document.querySelectorAll('[data-layer-preset]').forEach(function (btn) {
      var p = PRESETS[btn.getAttribute('data-layer-preset')];
      if (!p) return;
      var match = Object.keys(p).every(function (k) { return !!layerState[k] === !!p[k]; });
      btn.classList.toggle('active', match);
    });
    if (syncOverlays) {
      refreshAllLiveLinks();
      refreshLiveDrawer();
    }
  }

  function saveLayers() {
    try { localStorage.setItem(LAYER_KEY, JSON.stringify(layerState)); } catch (e) {}
  }

  syncLayers();

  document.addEventListener('change', function (e) {
    var k = e.target && e.target.getAttribute && e.target.getAttribute('data-k');
    if (!k) return;
    layerState[k] = e.target.checked;
    syncLayers();
    saveLayers();
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-layer-preset]');
    if (!btn) return;
    var p = PRESETS[btn.getAttribute('data-layer-preset')];
    if (!p) return;
    Object.keys(p).forEach(function (k) { layerState[k] = p[k]; });
    syncLayers();
    saveLayers();
  });

  // ---- Panel backdrop toggle (white / checker / dark) ----------------------
  var bgMode = 'light';
  try {
    var sb = localStorage.getItem(BG_KEY);
    if (sb === 'light' || sb === 'checker' || sb === 'dark') bgMode = sb;
  } catch (e) {}

  function applyBackdrop(mode) {
    bgMode = mode;
    document.body.classList.remove('bg-checker', 'bg-dark');
    if (mode === 'checker') document.body.classList.add('bg-checker');
    else if (mode === 'dark') document.body.classList.add('bg-dark');
    document.querySelectorAll('[data-backdrop]').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-backdrop') === mode);
    });
  }
  applyBackdrop(bgMode);

  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-backdrop]');
    if (!b) return;
    applyBackdrop(b.getAttribute('data-backdrop'));
    try { localStorage.setItem(BG_KEY, bgMode); } catch (err) {}
  });

  // ---- Copyable math/permutations buttons ----------------------------------
  function copyText(text, btn) {
    var done = function () {
      var orig = btn.getAttribute('data-orig-label') || btn.textContent;
      btn.setAttribute('data-orig-label', orig);
      btn.textContent = 'Copied \u2713';
      btn.classList.add('copied');
      clearTimeout(btn._copyTimer);
      btn._copyTimer = setTimeout(function () {
        btn.textContent = orig;
        btn.classList.remove('copied');
      }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        document.body.removeChild(ta);
      });
    } else {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
      document.body.removeChild(ta);
    }
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-copy]');
    if (!btn) return;
    copyText(btn.getAttribute('data-copy'), btn);
  });

  // ---- Live SymmHub links, Sync Overlays & Inline Live Preview Drawer ------
  var liveData = null;
  var liveScript = document.getElementById('entry-live-data');
  if (liveScript) {
    try { liveData = JSON.parse(liveScript.textContent); } catch (e) {}
  }

  function currentOverlayOpt(kind) {
    if (!syncOverlays) return { enabled: false };
    var isGroup = (kind === 'group');
    return {
      enabled: true,
      gfd: !!layerState.gfd,
      gtil: !!layerState.gtil,
      gsym: !!layerState.gsym,
      hfd: !isGroup && !!layerState.hfd,
      htil: !isGroup && !!layerState.htil,
      hsym: !isGroup && !!layerState.hsym,
    };
  }

  function liveUrlFor(kind, permIndex, uiMode) {
    if (!liveData || !window.CATALOG_LIVE) return null;
    var ov = currentOverlayOpt(kind);
    if (kind === 'group') {
      return window.CATALOG_LIVE.buildLiveUrl({
        app: liveData.app,
        preset: liveData.preset,
        siteRoot: liveData.siteRoot,
        layer: liveData.layer,
        title: liveData.group,
        n: 1,
        permutations: liveData.one,
        cosets: '',
        permIndex: 0,
        useOrbit: false,
        iterations: liveData.iterations,
        ui: uiMode || '',
        overlays: ov,
      });
    }
    var isOrbit = kind === 'orbit';
    var idx = Number(permIndex || 0);
    var suffix = isOrbit ? (idx > 0 ? '.o' + idx : '.o') : ('.' + (idx + 1));
    return window.CATALOG_LIVE.buildLiveUrl({
      app: liveData.app,
      preset: liveData.preset,
      siteRoot: liveData.siteRoot,
      layer: liveData.layer,
      title: liveData.name + suffix,
      n: liveData.n,
      permutations: isOrbit ? liveData.invcos : liveData.cosets,
      cosets: liveData.cosets,
      permIndex: idx,
      useOrbit: isOrbit,
      iterations: liveData.iterations,
      ui: uiMode || '',
      overlays: ov,
    });
  }

  refreshAllLiveLinks = function () {
    if (!liveData || !window.CATALOG_LIVE) return;
    document.querySelectorAll('a[data-live-kind]').forEach(function (a) {
      var u = liveUrlFor(
        a.getAttribute('data-live-kind'),
        a.getAttribute('data-live-perm'),
        a.getAttribute('data-live-ui')
      );
      if (u) a.href = u;
    });
    var syncBoxes = document.querySelectorAll('input[data-sync-overlays]');
    syncBoxes.forEach(function (cb) { cb.checked = syncOverlays; });
  };

  // Sync overlays checkboxes (in header and inside live drawer)
  document.addEventListener('change', function (e) {
    if (!e.target || !e.target.hasAttribute || !e.target.hasAttribute('data-sync-overlays')) return;
    syncOverlays = e.target.checked;
    try { localStorage.setItem(SYNC_OV_KEY, syncOverlays ? '1' : '0'); } catch (err) {}
    refreshAllLiveLinks();
    refreshLiveDrawer();
  });

  // Inline Live Preview Drawer
  var drawer = document.getElementById('live-drawer');
  var iframe = document.getElementById('live-iframe');
  var liveNewTab = document.getElementById('live-newtab');
  var liveStudioTab = document.getElementById('live-studiotab');
  var liveTallBtn = document.getElementById('live-tall');
  var drawerState = { open: false, kind: 'coset', perm: 0 };

  refreshLiveDrawer = function () {
    if (!drawer || !drawerState.open || !liveData || !window.CATALOG_LIVE) return;
    var uSimple = liveUrlFor(drawerState.kind, drawerState.perm, 'simple');
    var uStudio = liveUrlFor(drawerState.kind, drawerState.perm, '');
    if (iframe && uSimple && iframe.src !== uSimple) {
      iframe.src = uSimple;
    }
    if (liveNewTab && uSimple) liveNewTab.href = uSimple;
    if (liveStudioTab && uStudio) liveStudioTab.href = uStudio;
    drawer.querySelectorAll('[data-drawer-tab]').forEach(function (b) {
      var match = b.getAttribute('data-drawer-kind') === drawerState.kind &&
                  Number(b.getAttribute('data-drawer-perm') || 0) === Number(drawerState.perm || 0);
      b.classList.toggle('active', match);
    });
  };

  function openLiveDrawer(kind, perm) {
    if (!drawer || !liveData) return;
    drawerState.open = true;
    drawerState.kind = kind || 'coset';
    drawerState.perm = Number(perm || 0);
    drawer.hidden = false;
    refreshLiveDrawer();
    drawer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function closeLiveDrawer() {
    if (!drawer) return;
    drawerState.open = false;
    drawer.hidden = true;
    if (iframe) iframe.src = 'about:blank';
  }

  document.addEventListener('click', function (e) {
    var openBtn = e.target.closest && e.target.closest('[data-live-preview]');
    if (openBtn) {
      e.preventDefault();
      var k = openBtn.getAttribute('data-live-kind') || 'coset';
      var p = Number(openBtn.getAttribute('data-live-perm') || 0);
      if (drawerState.open && openBtn.id === 'hdr-live-btn') {
        closeLiveDrawer();
      } else {
        openLiveDrawer(k, p);
      }
      return;
    }
    var tabBtn = e.target.closest && e.target.closest('[data-drawer-tab]');
    if (tabBtn) {
      openLiveDrawer(tabBtn.getAttribute('data-drawer-kind'), tabBtn.getAttribute('data-drawer-perm'));
      return;
    }
    if (e.target.closest && e.target.closest('#live-close')) {
      closeLiveDrawer();
      return;
    }
    if (e.target.closest && e.target.closest('#live-tall')) {
      drawer.classList.toggle('tall');
      if (liveTallBtn) liveTallBtn.textContent = drawer.classList.contains('tall') ? 'Compact' : 'Tall';
    }
  });

  refreshAllLiveLinks();
  window.addEventListener('symmhubBaseChanged', function () {
    refreshAllLiveLinks();
    refreshLiveDrawer();
  });

  // ---- Partition table hover crosshairs & rep highlight --------------------
  var gridTable = document.querySelector('table.grid');
  if (gridTable) {
    var clearHighlights = function () {
      gridTable.querySelectorAll('.hl-row, .hl-col, .hl-rep').forEach(function (el) {
        el.classList.remove('hl-row', 'hl-col', 'hl-rep');
      });
    };
    gridTable.addEventListener('mouseover', function (e) {
      var td = e.target.closest('td.cell');
      if (!td) return;
      clearHighlights();
      var tr = td.parentNode;
      var col = td.cellIndex;
      if (tr) {
        var rth = tr.querySelector('th.row');
        if (rth) rth.classList.add('hl-row');
      }
      var headRow = gridTable.rows[0];
      if (headRow && headRow.cells[col]) {
        headRow.cells[col].classList.add('hl-col');
        var repIdx = headRow.cells[col].getAttribute('data-rep-col');
        if (repIdx !== null && headRow.cells[Number(repIdx) + 1]) {
          headRow.cells[Number(repIdx) + 1].classList.add('hl-rep');
        }
      }
    });
    gridTable.addEventListener('mouseleave', clearHighlights);

    document.querySelectorAll('table.action .sw[data-color-idx]').forEach(function (sw) {
      var cidx = Number(sw.getAttribute('data-color-idx'));
      sw.addEventListener('mouseenter', function () {
        clearHighlights();
        var row = gridTable.rows[cidx + 1];
        if (row) {
          var th = row.querySelector('th.row');
          if (th) th.classList.add('hl-row');
        }
      });
      sw.addEventListener('mouseleave', clearHighlights);
    });
  }

  // ---- Lightbox with 2D grid navigation, buttons, layer bar & live link ----
  var lb = document.getElementById('lb');
  var box = document.getElementById('lb-stack');
  var lbTitle = document.getElementById('lb-title');
  var lbMeta = document.getElementById('lb-meta');
  var lbLayers = document.getElementById('lb-layers');
  var lbLiveInline = document.getElementById('lb-live-inline');
  var lbLive = document.getElementById('lb-live');
  var lbLiveStudio = document.getElementById('lb-live-studio');
  var stacks = [].slice.call(document.querySelectorAll('.page-main .stack'));
  var idx = -1, pos = [], cellAt = {}, flow = [];

  stacks.forEach(function (s, i) {
    var td = s.closest('table.grid td');
    if (td) {
      var r = td.parentNode.rowIndex - 1, c = td.cellIndex - 1;
      pos[i] = [r, c];
      cellAt[r + ',' + c] = i;
    } else {
      pos[i] = null;
      flow.push(i);
    }
  });

  function updateNavButtons() {
    var p = pos[idx];
    var setDis = function (id, ok) {
      var b = document.getElementById(id);
      if (b) b.disabled = !ok;
    };
    if (p) {
      setDis('lb-up', cellAt[(p[0] - 1) + ',' + p[1]] !== undefined);
      setDis('lb-dn', cellAt[(p[0] + 1) + ',' + p[1]] !== undefined);
      setDis('lb-lt', cellAt[p[0] + ',' + (p[1] - 1)] !== undefined);
      setDis('lb-rt', cellAt[p[0] + ',' + (p[1] + 1)] !== undefined);
    } else {
      var k = flow.indexOf(idx);
      setDis('lb-up', false);
      setDis('lb-dn', false);
      setDis('lb-lt', k > 0);
      setDis('lb-rt', k >= 0 && k < flow.length - 1);
    }
  }

  function show(i) {
    if (i === undefined || i < 0 || i >= stacks.length) return;
    idx = i;
    var s = stacks[i];
    box.innerHTML = s.innerHTML;
    box.querySelectorAll('img[loading="lazy"]').forEach(function (img) {
      img.removeAttribute('loading');
    });
    var cap = s.querySelector('.cap');
    if (lbTitle) lbTitle.innerHTML = cap ? cap.innerHTML : '';
    var p = pos[i];
    if (lbMeta) {
      lbMeta.textContent = p
        ? ('Partition table \u00b7 row ' + (p[0] + 1) + ', col ' + (p[1] + 1))
        : ((flow.indexOf(i) + 1) + ' / ' + flow.length);
    }
    if (lbLayers) lbLayers.hidden = !p;
    var lKind = s.getAttribute('data-live-kind');
    var lPerm = s.getAttribute('data-live-perm');
    if (lbLive && lbLiveStudio) {
      if (lKind && liveData && window.CATALOG_LIVE) {
        lbLive.href = liveUrlFor(lKind, lPerm, 'simple');
        lbLiveStudio.href = liveUrlFor(lKind, lPerm, '');
        lbLive.setAttribute('data-live-kind', lKind);
        lbLive.setAttribute('data-live-perm', lPerm || '0');
        lbLiveStudio.setAttribute('data-live-kind', lKind);
        lbLiveStudio.setAttribute('data-live-perm', lPerm || '0');
        lbLive.hidden = false;
        lbLiveStudio.hidden = false;
        if (lbLiveInline) {
          lbLiveInline.setAttribute('data-live-kind', lKind);
          lbLiveInline.setAttribute('data-live-perm', lPerm || '0');
          lbLiveInline.hidden = false;
        }
      } else {
        lbLive.hidden = true;
        lbLiveStudio.hidden = true;
        if (lbLiveInline) lbLiveInline.hidden = true;
      }
    }
    updateNavButtons();
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function hide() {
    lb.hidden = true;
    box.innerHTML = '';
    idx = -1;
    document.body.style.overflow = '';
  }

  function move(dr, dc) {
    var p = pos[idx];
    if (p) {
      show(cellAt[(p[0] + dr) + ',' + (p[1] + dc)]);
    } else if (!dr) {
      var k = flow.indexOf(idx) + dc;
      if (k >= 0 && k < flow.length) show(flow[k]);
    }
  }

  stacks.forEach(function (s, i) {
    s.tabIndex = 0;
    s.setAttribute('role', 'button');
    s.addEventListener('click', function () { show(i); });
    s.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(i); }
    });
  });

  if (lb) {
    lb.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('#lb-live-inline')) {
        var b = e.target.closest('#lb-live-inline');
        var k = b.getAttribute('data-live-kind');
        var p = b.getAttribute('data-live-perm');
        hide();
        openLiveDrawer(k, p);
        return;
      }
      if (e.target === lb || e.target === box || e.target.closest('#lb-close')) hide();
    });
    var bindDir = function (id, dr, dc) {
      var b = document.getElementById(id);
      if (b) b.addEventListener('click', function (e) { e.stopPropagation(); move(dr, dc); });
    };
    bindDir('lb-up', -1, 0);
    bindDir('lb-dn', 1, 0);
    bindDir('lb-lt', 0, -1);
    bindDir('lb-rt', 0, 1);
  }

  document.addEventListener('keydown', function (e) {
    var tag = e.target && e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    var searchModal = document.getElementById('cat-search-modal');
    if (searchModal && !searchModal.hidden) return;
    if (lb && !lb.hidden) {
      if (e.key === 'Escape') { hide(); return; }
      var d = { ArrowRight: [0, 1], ArrowLeft: [0, -1], ArrowDown: [1, 0], ArrowUp: [-1, 0] }[e.key];
      if (!d) return;
      e.preventDefault();
      move(d[0], d[1]);
      return;
    }
    if (e.key === '[') {
      var prev = document.querySelector('a[rel="prev"]');
      if (prev) location.href = prev.href;
    } else if (e.key === ']') {
      var next = document.querySelector('a[rel="next"]');
      if (next) location.href = next.href;
    }
  });
})();
