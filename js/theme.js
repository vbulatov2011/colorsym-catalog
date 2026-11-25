/* theme.js — Shared runtime for every catalog page:
 * - Zero-flash Light / Dark / System theme switcher (shared key 'symmhub_theme')
 * - Live SymmHub URL builder (with optional overlay sync & configurable base URL)
 * - Global quick-jump search modal (/ or Ctrl+K) backed by search_index.json
 * - Top-bar catalog version switcher backed by versions/index.json
 * - SymmHub live-URL settings popover (localStorage + optional catalog_config.json) */
(function () {
  var THEME_KEY = 'symmhub_theme';
  var SYM_URL_KEY = 'colorsym_symmhub_url';
  var MODES = ['light', 'dark', 'system'];
  var LABELS = {
    light:  { icon: '\u2600', text: 'Light',  title: 'Theme: Light (click for Dark)' },
    dark:   { icon: '\u263E', text: 'Dark',   title: 'Theme: Dark (click for System)' },
    system: { icon: '\u25D0', text: 'System', title: 'Theme: System (click for Light)' },
  };

  function readMode() {
    try {
      var v = localStorage.getItem(THEME_KEY);
      return MODES.indexOf(v) >= 0 ? v : 'light';
    } catch (e) {
      return 'light';
    }
  }

  function applyMode(mode) {
    document.documentElement.dataset.theme = mode;
    var info = LABELS[mode] || LABELS.light;
    var btns = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].textContent = info.icon + ' ' + info.text;
      btns[i].title = info.title;
      btns[i].setAttribute('aria-label', info.title);
    }
  }

  function setMode(mode) {
    try { localStorage.setItem(THEME_KEY, mode); } catch (e) {}
    applyMode(mode);
  }

  function cycleMode() {
    var cur = readMode();
    setMode(MODES[(MODES.indexOf(cur) + 1) % MODES.length]);
  }

  applyMode(readMode());

  // ---- Meta helpers --------------------------------------------------------

  function metaContent(name, fallback) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return (el && el.content !== undefined && el.content !== null) ? el.content : (fallback || '');
  }

  function siteRoot() {
    return metaContent('catalog-root', '');
  }

  // ---- Live SymmHub URL & optional catalog_config.json ---------------------

  var runtimeDefaultBase = null;
  var hideLiveSettings = metaContent('symmhub-settings', '1') === '0';

  function resolveSymmHubBase(raw, sRoot) {
    var clean = (raw || '').trim();
    if (!clean) return '';
    if (/^https?:\/\//i.test(clean)) return clean.replace(/\/+$/, '');
    try {
      var rootHref = new URL((sRoot !== undefined ? sRoot : siteRoot()) || './', location.href).href;
      return new URL(clean, rootHref).href.replace(/\/+$/, '');
    } catch (e) {
      return clean.replace(/\/+$/, '');
    }
  }

  function defaultSymmHubBase() {
    if (runtimeDefaultBase) return resolveSymmHubBase(runtimeDefaultBase);
    var m = metaContent('symmhub-base', '');
    return resolveSymmHubBase(m || 'http://localhost:8125');
  }

  function getSymmHubBase() {
    if (!hideLiveSettings) {
      try {
        var custom = localStorage.getItem(SYM_URL_KEY);
        if (custom) return resolveSymmHubBase(custom);
      } catch (e) {}
    }
    return defaultSymmHubBase();
  }

  function setSymmHubBase(url) {
    var clean = (url || '').trim().replace(/\/+$/, '');
    try {
      if (clean) localStorage.setItem(SYM_URL_KEY, clean);
      else localStorage.removeItem(SYM_URL_KEY);
    } catch (e) {}
    window.dispatchEvent(new CustomEvent('symmhubBaseChanged', { detail: { base: getSymmHubBase() } }));
  }

  function resolvePresetUrl(presetRel, sRoot, base) {
    if (!presetRel) return '';
    if (/^https?:\/\//i.test(presetRel) || presetRel.charAt(0) === '/') return presetRel;
    try {
      var baseUrl = new URL(base, location.href);
      var isLocal = /^(localhost|127\.0\.0\.1)$/i.test(baseUrl.hostname);
      var isCrossOrigin = baseUrl.origin !== location.origin;
      if (isLocal && isCrossOrigin && (baseUrl.pathname === '/' || baseUrl.pathname === '')) {
        return '/catalog/' + presetRel.replace(/^\/+/, '');
      }
    } catch (e) {}
    try {
      return new URL((sRoot || '') + presetRel, location.href).href;
    } catch (e) {
      return '/catalog/' + presetRel.replace(/^\/+/, '');
    }
  }

  /**
   * Build overlay layer patch for SymmHub's VisualizationOverlay from catalog
   * layer checkboxes (gfd, hfd, gtil, htil, gsym, hsym) + cosets string.
   */
  function buildOverlayPatch(ov, cosets) {
    if (!ov || !ov.enabled) return { enabled: false };
    var subSym = cosets ? { type: 'subgroup', cosets: cosets } : { type: 'renderer', cosets: '' };
    var gSym = { type: 'renderer', cosets: '' };
    var tilingOn = !!(ov.htil || ov.gtil);
    var fdOn = !!(ov.hfd || ov.gfd);
    var genOn = !!(ov.hsym || ov.gsym);
    if (!tilingOn && !fdOn && !genOn) return { enabled: false };
    return {
      enabled: true,
      overlays: {
        tiling: { enabled: tilingOn, symmetry: ov.htil ? subSym : gSym },
        fundDomain: {
          enabled: fdOn,
          fill: { enabled: fdOn },
          outline: { enabled: fdOn },
          symmetry: ov.hfd ? subSym : gSym,
        },
        generators: { enabled: genOn, symmetry: ov.hsym ? subSym : gSym },
      },
    };
  }

  /**
   * Build a deep link into SymmHub's SymDraw app for a color group coloring
   * (or an uncolored group motif when n === 1).
   *
   * opt = { app, preset, siteRoot, layer, title, n, permutations, cosets,
   *         permIndex, useOrbit, iterations, ui, overlays }
   */
  function buildLiveUrl(opt) {
    var base = getSymmHubBase();
    var appPath = opt.app || '/apps/symdraw/symdraw_wp.html';
    var presetUrl = resolvePresetUrl(opt.preset, opt.siteRoot, base);
    var layerId = opt.layer || 'drawing';
    var layerPatch = {
      coloringType: 'mult',
      permutations: opt.permutations,
      permIndex: opt.permIndex || 0,
      useOrbit: !!opt.useOrbit,
      mask: '',
      useMipmap: true,
      colorTiles: { count: opt.n || 1 },
    };
    var hashObj = {
      preset: presetUrl,
      title: opt.title || '',
      layers: {
        overlay: buildOverlayPatch(opt.overlays, opt.cosets || opt.permutations),
      },
    };
    hashObj.layers[layerId] = layerPatch;
    if (opt.iterations) {
      hashObj.params = { symmetry: { options: { iterations: opt.iterations } } };
    }
    if (opt.projection === 'sphere' || opt.projection === 'stereo') {
      hashObj.params = hashObj.params || {};
      var trPatch = { spherical: { enabled: opt.projection === 'sphere' } };
      if (opt.projection === 'sphere') trPatch.euclidean = { zoom: 0.92 };
      hashObj.params.tools = { transform: { params: trPatch } };
    }
    var q = opt.ui ? ('?ui=' + encodeURIComponent(opt.ui)) : '';
    return base + appPath + q + '#' + encodeURIComponent(JSON.stringify(hashObj));
  }

  window.CATALOG_LIVE = {
    getSymmHubBase: getSymmHubBase,
    setSymmHubBase: setSymmHubBase,
    defaultSymmHubBase: defaultSymmHubBase,
    buildLiveUrl: buildLiveUrl,
  };

  // ---- Topbar Enhancements (Search, Version Switcher, Live Settings) -------

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }

  function dispSym(s) {
    return esc(s).replace(/x/g, '\u00d7');
  }

  function mountSearchModal(actionsEl) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn sm';
    btn.id = 'cat-search-btn';
    btn.title = 'Quick jump to any group or color group (/ or Ctrl+K)';
    btn.innerHTML = '&#128269; Search <span class="kbd">/</span>';
    actionsEl.insertBefore(btn, actionsEl.firstChild);

    var modal = document.createElement('div');
    modal.id = 'cat-search-modal';
    modal.hidden = true;
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Quick jump catalog search');
    modal.innerHTML =
      '<div class="csm-dialog">' +
      '  <div class="csm-head">' +
      '    <span aria-hidden="true">&#128269;</span>' +
      '    <input type="search" id="csm-input" placeholder="Jump to group or color group (e.g. p6m, 632 3, 333 normal, *442)\u2026" autocomplete="off">' +
      '    <button type="button" class="btn sm" id="csm-close">Esc</button>' +
      '  </div>' +
      '  <div class="csm-list" id="csm-list"></div>' +
      '  <div class="csm-foot"><span>&uarr;&darr; navigate &middot; Enter open &middot; Esc close</span><span id="csm-count"></span></div>' +
      '</div>';
    document.body.appendChild(modal);

    var input = modal.querySelector('#csm-input');
    var listEl = modal.querySelector('#csm-list');
    var countEl = modal.querySelector('#csm-count');
    var itemsCache = null;
    var loading = false;
    var activeIdx = 0;
    var shownItems = [];

    function versionPrefix() {
      var v = metaContent('catalog-version', '');
      var isMain = metaContent('catalog-is-main', '1') !== '0';
      return (!isMain && v) ? ('versions/' + encodeURIComponent(v) + '/') : '';
    }

    function loadIndex() {
      if (itemsCache || loading) return;
      loading = true;
      listEl.innerHTML = '<div class="csm-empty">Loading search index\u2026</div>';
      var sRoot = siteRoot();
      var url = sRoot + versionPrefix() + 'search_index.json';
      fetch(url).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (d) {
        itemsCache = d.items || [];
        loading = false;
        renderResults();
      }).catch(function () {
        // Fallback to root search_index.json if version-specific copy is absent
        fetch(sRoot + 'search_index.json').then(function (r) { return r.json(); }).then(function (d) {
          itemsCache = d.items || [];
          loading = false;
          renderResults();
        }).catch(function () {
          loading = false;
          listEl.innerHTML = '<div class="csm-empty">Search index not available.</div>';
        });
      });
    }

    function scoreItem(it, tokens) {
      var hay = it._hay;
      for (var i = 0; i < tokens.length; i++) {
        if (hay.indexOf(tokens[i]) < 0) return -1;
      }
      var score = it.k === 'g' ? 20 : 10;
      var q0 = tokens[0] || '';
      if (q0) {
        var nm = it.n.toLowerCase();
        if (nm === q0 || (it.hm && it.hm.toLowerCase() === q0)) score += 100;
        else if (nm.indexOf(q0) === 0 || (it.hm && it.hm.toLowerCase().indexOf(q0) === 0)) score += 40;
      }
      return score;
    }

    function renderResults() {
      if (!itemsCache) return;
      var raw = input.value.trim().toLowerCase().replace(/\u00d7/g, 'x');
      var tokens = raw ? raw.split(/\s+/).filter(Boolean) : [];
      var famsSeen = {};
      for (var fi = 0; fi < itemsCache.length; fi++) famsSeen[itemsCache[fi].f || 'wp'] = true;
      var multiFam = Object.keys(famsSeen).length > 1;
      var matched = [];
      for (var i = 0; i < itemsCache.length; i++) {
        var it = itemsCache[i];
        if (!it._hay) {
          var asciiName = it.n.replace(/\u221e/g, 'oo');
          it._hay = [
            it.n, asciiName, asciiName.replace(/\*/g, 's'),
            it.hm || '', it.h || '', (it.h || '').replace(/\u221e/g, 'oo'),
            it.f || '',
            it.c ? (it.c + ' colors ' + it.c + 'c') : '',
            it.norm ? 'normal' : '',
            it.p ? (it.p + ' placements') : '',
          ].join(' ').toLowerCase();
        }
        if (!tokens.length) {
          if (it.k === 'g') matched.push({ it: it, s: 10 });
        } else {
          var sc = scoreItem(it, tokens);
          if (sc >= 0) matched.push({ it: it, s: sc });
        }
      }
      if (tokens.length) {
        matched.sort(function (a, b) {
          return (b.s - a.s) || ((a.it.c || 0) - (b.it.c || 0)) || a.it.n.localeCompare(b.it.n, undefined, { numeric: true });
        });
      }
      var total = matched.length;
      shownItems = matched.slice(0, 60).map(function (x) { return x.it; });
      activeIdx = 0;
      countEl.textContent = tokens.length
        ? (total + ' match' + (total === 1 ? '' : 'es') + (total > 60 ? ' (showing top 60)' : ''))
        : (shownItems.length + ' groups (type to search all ' + itemsCache.length + ' entries)');
      if (!shownItems.length) {
        listEl.innerHTML = '<div class="csm-empty">No matching group or color group.</div>';
        return;
      }
      var sRoot = siteRoot();
      listEl.innerHTML = shownItems.map(function (it, idx) {
        var href = sRoot + it.u;
        var famTag = multiFam && it.f ? '<span class="badge">' + esc(it.f) + '</span>' : '';
        var badges = '';
        if (it.k === 'g') {
          badges = famTag + '<span class="badge">group</span><span>' + esc(it.info || '') + '</span>';
        } else {
          badges = famTag + (it.norm ? '<span class="badge on">normal</span>' : '') +
                   '<span>' + it.c + 'c &middot; ' + it.p + 'p</span>';
        }
        return '<a class="csm-item' + (idx === 0 ? ' sel' : '') + '" href="' + esc(href) + '" data-idx="' + idx + '">' +
               '<span class="csm-main"><span class="csm-name">' + dispSym(it.n) + '</span>' +
               (it.hm ? '<span class="csm-hm">' + esc(it.hm) + '</span>' : '') + '</span>' +
               '<span class="csm-meta">' + badges + '</span></a>';
      }).join('');
    }

    function updateSel(next) {
      if (!shownItems.length) return;
      activeIdx = Math.max(0, Math.min(shownItems.length - 1, next));
      var els = listEl.querySelectorAll('.csm-item');
      els.forEach(function (el, i) { el.classList.toggle('sel', i === activeIdx); });
      if (els[activeIdx]) els[activeIdx].scrollIntoView({ block: 'nearest' });
    }

    function openModal() {
      modal.hidden = false;
      loadIndex();
      input.focus();
      input.select();
      if (itemsCache) renderResults();
    }

    function closeModal() {
      modal.hidden = true;
    }

    btn.addEventListener('click', openModal);
    modal.querySelector('#csm-close').addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
    input.addEventListener('input', renderResults);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); closeModal(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); updateSel(activeIdx + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); updateSel(activeIdx - 1); }
      else if (e.key === 'Enter') {
        var sel = listEl.querySelector('.csm-item.sel');
        if (sel) { e.preventDefault(); location.href = sel.href; }
      }
    });

    document.addEventListener('keydown', function (e) {
      var tag = e.target && e.target.tagName;
      var inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (modal.hidden) openModal(); else closeModal();
      } else if (e.key === '/' && !inField && modal.hidden) {
        e.preventDefault();
        openModal();
      } else if (e.key === 'Escape' && !modal.hidden) {
        closeModal();
      }
    });
  }

  function mountVersionSwitcher(actionsEl) {
    if (metaContent('catalog-versions', '0') !== '1') return;
    var rel = metaContent('catalog-rel', '');
    var curVer = metaContent('catalog-version', '');
    var curFam = metaContent('catalog-family', 'wp');
    if (!rel || !curVer) return;
    var sRoot = siteRoot();
    fetch(sRoot + 'versions/index.json', { cache: 'no-store' }).then(function (r) {
      if (!r.ok) return null;
      return r.json();
    }).then(function (reg) {
      if (!reg || !reg.versions) return;
      var vnames = Object.keys(reg.versions).filter(function (v) {
        return (reg.versions[v].family || 'wp') === curFam;
      });
      if (vnames.length < 2) return;
      var famMain = (reg.mainByFamily && reg.mainByFamily[curFam]) || reg.main;
      var sel = document.createElement('select');
      sel.className = 'ver-select';
      sel.setAttribute('aria-label', 'Switch catalog version');
      sel.title = 'Switch catalog version on this page';
      vnames.forEach(function (v) {
        var opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v + (v === famMain ? ' (main)' : '');
        if (v === curVer) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener('change', function () {
        var targetV = sel.value;
        var dest = (targetV === famMain)
          ? (sRoot + rel)
          : (sRoot + 'versions/' + encodeURIComponent(targetV) + '/' + rel);
        location.href = dest;
      });
      var themeBtn = actionsEl.querySelector('[data-theme-toggle]');
      if (themeBtn) actionsEl.insertBefore(sel, themeBtn);
      else actionsEl.appendChild(sel);
    }).catch(function () {});
  }

  function mountLiveSettings(actionsEl) {
    var wrap = document.createElement('div');
    wrap.className = 'settings-wrap';
    wrap.innerHTML =
      '<button type="button" class="btn sm" id="sym-settings-btn" title="Configure live SymmHub URL" aria-label="SymmHub URL settings">&#9881;</button>' +
      '<div class="settings-pop" id="sym-settings-pop" hidden>' +
      '  <h3>Live SymmHub URL</h3>' +
      '  <p>Base URL used by <b>Explore</b>, <b>Studio</b>, and <b>Live preview</b> links. Saved in browser storage.</p>' +
      '  <input type="url" id="sym-url-in" placeholder="http://localhost:8125">' +
      '  <div class="set-row">' +
      '    <button type="button" class="btn sm primary" id="sym-url-save">Save</button>' +
      '    <button type="button" class="btn sm" id="sym-url-local">Local :8125</button>' +
      '    <button type="button" class="btn sm" id="sym-url-origin">Same origin</button>' +
      '    <button type="button" class="btn sm" id="sym-url-test">Test</button>' +
      '    <button type="button" class="btn sm" id="sym-url-reset">Reset</button>' +
      '  </div>' +
      '  <div class="set-status" id="sym-url-status"></div>' +
      '</div>';
    actionsEl.appendChild(wrap);

    var btn = wrap.querySelector('#sym-settings-btn');
    var pop = wrap.querySelector('#sym-settings-pop');
    var inp = wrap.querySelector('#sym-url-in');
    var st = wrap.querySelector('#sym-url-status');

    function setSt(text, cls) {
      st.textContent = text || '';
      st.className = 'set-status' + (cls ? ' ' + cls : '');
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      pop.hidden = !pop.hidden;
      if (!pop.hidden) {
        inp.value = getSymmHubBase();
        setSt('');
        inp.focus();
      }
    });
    document.addEventListener('click', function (e) {
      if (!pop.hidden && !wrap.contains(e.target)) pop.hidden = true;
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !pop.hidden) pop.hidden = true;
    });

    wrap.querySelector('#sym-url-save').addEventListener('click', function () {
      setSymmHubBase(inp.value);
      setSt('Saved: ' + getSymmHubBase(), 'ok');
    });
    wrap.querySelector('#sym-url-local').addEventListener('click', function () {
      inp.value = 'http://localhost:8125';
      setSymmHubBase(inp.value);
      setSt('Set to local SymmHub (:8125)', 'ok');
    });
    wrap.querySelector('#sym-url-origin').addEventListener('click', function () {
      inp.value = location.origin;
      setSymmHubBase(inp.value);
      setSt('Set to ' + location.origin, 'ok');
    });
    wrap.querySelector('#sym-url-reset').addEventListener('click', function () {
      setSymmHubBase('');
      inp.value = getSymmHubBase();
      setSt('Reset to default (' + getSymmHubBase() + ')', 'ok');
    });
    wrap.querySelector('#sym-url-test').addEventListener('click', function () {
      var u = resolveSymmHubBase(inp.value || getSymmHubBase()) + '/apps/symdraw/symdraw_wp.html';
      setSt('Checking ' + u + '\u2026');
      fetch(u, { method: 'GET' }).then(function (r) {
        if (r.ok) setSt('Reachable (HTTP ' + r.status + ')', 'ok');
        else setSt('Server responded HTTP ' + r.status, 'err');
      }).catch(function () {
        setSt('Could not reach ' + u + ' (start tools/serve_symmhub.mjs or check CORS)', 'err');
      });
    });
  }

  function applySettingsVisibility() {
    if (!hideLiveSettings) return;
    var wrap = document.querySelector('.settings-wrap');
    if (wrap) wrap.hidden = true;
    document.querySelectorAll('.live-foot span').forEach(function (sp) {
      if (sp.id !== 'live-foot-hint' && /SymmHub URL/i.test(sp.textContent || '')) {
        sp.hidden = true;
      }
    });
  }

  function loadOptionalConfig() {
    var sRoot = siteRoot();
    fetch(sRoot + 'catalog_config.json', { cache: 'no-store' }).then(function (r) {
      return r.ok ? r.json() : null;
    }).then(function (cfg) {
      if (!cfg) return;
      var changed = false;
      if (cfg.hideSymmhubSettings === true) {
        hideLiveSettings = true;
        applySettingsVisibility();
        changed = true;
      }
      if (cfg.symmhubUrl) {
        runtimeDefaultBase = cfg.symmhubUrl.trim().replace(/\/+$/, '');
        changed = true;
      }
      if (changed) {
        window.dispatchEvent(new CustomEvent('symmhubBaseChanged', { detail: { base: getSymmHubBase() } }));
      }
    }).catch(function () {});
  }

  function initUI() {
    var btns = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < btns.length; i++) {
      if (!btns[i].dataset.themeBound) {
        btns[i].dataset.themeBound = '1';
        btns[i].addEventListener('click', cycleMode);
      }
    }
    applyMode(readMode());

    var actionsEl = document.querySelector('.topnav__actions');
    if (actionsEl) {
      mountSearchModal(actionsEl);
      mountVersionSwitcher(actionsEl);
      if (!hideLiveSettings) mountLiveSettings(actionsEl);
    }
    applySettingsVisibility();
    loadOptionalConfig();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUI);
  } else {
    initUI();
  }

  window.addEventListener('storage', function (e) {
    if (e && e.key === THEME_KEY) applyMode(readMode());
    if (e && e.key === SYM_URL_KEY) {
      window.dispatchEvent(new CustomEvent('symmhubBaseChanged', { detail: { base: getSymmHubBase() } }));
    }
  });
})();
