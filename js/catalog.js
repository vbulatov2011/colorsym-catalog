/* catalog.js — Progressive enhancement for family, group, and count index pages:
 * - Instant client-side search & filtering (symbol/HM/subgroup H, normal-only, placements)
 * - Sticky group-jump chip highlighting on all-symmetries count pages
 * - Live SymmHub motif link wiring on group hero pages */
(function () {
  // ---- Group hero live link ------------------------------------------------
  var liveEl = document.getElementById('group-live-data');
  if (liveEl && window.CATALOG_LIVE) {
    try {
      var cfg = JSON.parse(liveEl.textContent);
      var refreshGroupLive = function () {
        document.querySelectorAll('[data-live-group]').forEach(function (a) {
          var mode = a.getAttribute('data-live-group');
          a.href = window.CATALOG_LIVE.buildLiveUrl({
            app: cfg.app,
            preset: cfg.preset,
            siteRoot: cfg.siteRoot,
            layer: cfg.layer,
            title: cfg.name,
            n: 1,
            permutations: cfg.trivial,
            permIndex: 0,
            useOrbit: false,
            ui: mode === 'simple' ? 'simple' : '',
          });
        });
      };
      refreshGroupLive();
      window.addEventListener('symmhubBaseChanged', refreshGroupLive);
    } catch (e) {}
  }

  // ---- Family index search (wp/index.html) ---------------------------------
  var famInput = document.getElementById('fam-search');
  if (famInput) {
    var famCount = document.getElementById('fam-count');
    var cards = [].slice.call(document.querySelectorAll('.grid .card[data-search]'));
    var sections = [].slice.call(document.querySelectorAll('section.fam-sec'));
    function filterFam() {
      var q = famInput.value.trim().toLowerCase();
      var shown = 0;
      cards.forEach(function (c) {
        var hay = (c.getAttribute('data-search') || '').toLowerCase();
        var ok = !q || hay.indexOf(q) >= 0;
        c.hidden = !ok;
        if (ok) shown++;
      });
      sections.forEach(function (sec) {
        var any = sec.querySelector('.card:not([hidden])');
        sec.hidden = !any;
      });
      if (famCount) {
        famCount.textContent = q
          ? (shown + ' of ' + cards.length + ' groups')
          : (cards.length + ' groups');
      }
    }
    famInput.addEventListener('input', filterFam);
    filterFam();
  }

  // ---- Color-group filter (group page, count page, all-symmetries page) ----
  var cgBar = document.getElementById('cg-filter');
  if (cgBar) {
    var qIn = document.getElementById('cg-q');
    var hSel = document.getElementById('cg-h');
    var kSel = document.getElementById('cg-k');
    var normCb = document.getElementById('cg-norm');
    var clearBtn = document.getElementById('cg-clear');
    var outCount = document.getElementById('cg-count');
    var boxes = [].slice.call(document.querySelectorAll('.cg[data-name]'));
    var frames = [].slice.call(document.querySelectorAll('.tframe'));
    var countSecs = [].slice.call(document.querySelectorAll('section.cg-sec'));

    // Populate distinct subgroup H types into the selector if present
    if (hSel) {
      var hSet = {};
      boxes.forEach(function (b) {
        var h = b.getAttribute('data-h');
        if (h) hSet[h] = (hSet[h] || 0) + 1;
      });
      Object.keys(hSet).sort().forEach(function (h) {
        var o = document.createElement('option');
        o.value = h;
        o.textContent = 'H = ' + h.replace(/x/g, '\u00d7') + ' (' + hSet[h] + ')';
        hSel.appendChild(o);
      });
    }

    function applyFilter() {
      var q = qIn ? qIn.value.trim().toLowerCase() : '';
      var hVal = hSel ? hSel.value : '';
      var kVal = kSel ? kSel.value : '';
      var normOnly = normCb ? normCb.checked : false;
      var active = !!(q || hVal || kVal || normOnly);
      var shown = 0;

      boxes.forEach(function (b) {
        var ok = true;
        if (q) {
          var hay = (b.getAttribute('data-search') || '').toLowerCase();
          if (hay.indexOf(q) < 0) ok = false;
        }
        if (ok && hVal && b.getAttribute('data-h') !== hVal) ok = false;
        if (ok && normOnly && b.getAttribute('data-normal') !== '1') ok = false;
        if (ok && kVal) {
          var k = Number(b.getAttribute('data-k') || '1');
          if (kVal === '1' && k !== 1) ok = false;
          else if (kVal === '2+' && k < 2) ok = false;
          else if (kVal === '3+' && k < 3) ok = false;
        }
        b.hidden = !ok;
        if (ok) shown++;
      });

      frames.forEach(function (fr) {
        fr.hidden = !fr.querySelector('.cg:not([hidden])');
      });

      countSecs.forEach(function (sec) {
        if (!active) {
          sec.hidden = false;
        } else {
          sec.hidden = !sec.querySelector('.cg:not([hidden])');
        }
      });

      if (clearBtn) clearBtn.hidden = !active;
      if (outCount) {
        outCount.textContent = active
          ? ('Showing ' + shown + ' of ' + boxes.length + ' color groups')
          : (boxes.length + ' color groups');
      }
    }

    [qIn, hSel, kSel, normCb].forEach(function (el) {
      if (!el) return;
      el.addEventListener(el.type === 'search' ? 'input' : 'change', applyFilter);
    });
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        if (qIn) qIn.value = '';
        if (hSel) hSel.value = '';
        if (kSel) kSel.value = '';
        if (normCb) normCb.checked = false;
        applyFilter();
        if (qIn) qIn.focus();
      });
    }
    applyFilter();
  }

  // ---- Sticky group-jump chip highlighting (colors/<N>/index.html) ---------
  var jumpBar = document.querySelector('.jump-chips');
  if (jumpBar && 'IntersectionObserver' in window) {
    var chipMap = {};
    jumpBar.querySelectorAll('a[href^="#"]').forEach(function (a) {
      chipMap[a.getAttribute('href').slice(1)] = a;
    });
    var headings = [].slice.call(document.querySelectorAll('h2.sec.cnt[id]'));
    if (headings.length) {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          Object.keys(chipMap).forEach(function (id) {
            chipMap[id].classList.toggle('active', id === en.target.id);
          });
        });
      }, { rootMargin: '-15% 0px -70% 0px', threshold: 0 });
      headings.forEach(function (h) { obs.observe(h); });
    }
  }
})();
