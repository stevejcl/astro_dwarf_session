/* =====================================================================
   "My Dwarf list" - the user's own choice of catalogue objects (1 to 5),
   programmed to the Dwarf like the Best-of-Tonight plan (user-requested
   Oct 2026).

   - The object detail pane gets a "+ Dwarf list" button next to
     "Plan mosaic" (added when that button appears - no change to the
     catalog's own render code).
   - A floating chip "Dwarf list (n/5)" opens the list: remove an object,
     or "Program to the Dwarf".
   - The plans are built with the catalog's own Best-of-Tonight pieces:
     the site's night window (astroNightWindow, anchored at local noon of
     the night's date, as the plan does), _planComputeUsableHours,
     peakAltitudeTonight and _planBuildPlan (filter + exposure / gain
     recommendation for the rig). Then the same openDwarfProgramPanel()
     as the plan's "Program session to the Dwarf" button.
   - Rig: the catalogue's rig filter when it is a Dwarf (D3 / DMINI),
     else Dwarf 3.

   Uses catalog.html globals (classic script, same global scope):
   _mosaicTarget, ATLAS_FULL, RIG_GROUPS, filterRig, getActiveLocation,
   getActiveLocationId, astroNightWindow, _planComputeUsableHours,
   peakAltitudeTonight, _planBuildPlan, pickerSampleDate, getNightDef,
   window.openDwarfProgramPanel (js/dwarf-scheduler.js).
   ===================================================================== */

var DWSEL_KEY = 'dso_dwarf_selection';
var DWSEL_MAX = 5;

function _dwselLoad() {
  try { var v = JSON.parse(localStorage.getItem(DWSEL_KEY)); return Array.isArray(v) ? v.slice(0, DWSEL_MAX) : []; }
  catch (e) { return []; }
}
function _dwselSave(list) {
  try { localStorage.setItem(DWSEL_KEY, JSON.stringify(list.slice(0, DWSEL_MAX))); } catch (e) {}
  _dwselRenderChip();
}
function _dwselEsc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
function _dwselToast(msg) {
  var t = document.getElementById('dwsel-toast');
  if (!t) {
    t = document.createElement('div'); t.id = 'dwsel-toast';
    t.style.cssText = 'position:fixed;left:50%;bottom:70px;transform:translateX(-50%);z-index:2600;background:var(--bg3,#1b2638);' +
      'color:var(--text,#e6eefb);border:1px solid var(--border2,#33415c);border-radius:8px;padding:8px 14px;font-size:13px;' +
      'opacity:0;transition:opacity .2s;pointer-events:none';
    document.body.appendChild(t);
  }
  t.textContent = msg; t.style.opacity = '1';
  clearTimeout(t._h); t._h = setTimeout(function () { t.style.opacity = '0'; }, 2200);
}

/* ---------- add from the detail pane ---------- */
function _dwselAddCurrent() {
  var tgt = (typeof _mosaicTarget === 'function') ? _mosaicTarget() : null;
  if (!tgt || !tgt.id) { _dwselToast('Select an object first.'); return; }
  var list = _dwselLoad();
  if (list.some(function (o) { return o.id === tgt.id; })) { _dwselToast(tgt.name + ' is already in the Dwarf list.'); return; }
  if (list.length >= DWSEL_MAX) { _dwselToast('The Dwarf list holds ' + DWSEL_MAX + ' objects at most.'); return; }
  list.push({ id: tgt.id, name: tgt.name || tgt.id, ra: tgt.raH, dec: tgt.dec });
  _dwselSave(list);
  _dwselToast(tgt.name + ' added to the Dwarf list (' + list.length + '/' + DWSEL_MAX + ').');
}

// "+ Dwarf list" next to each "Plan mosaic" button the catalog renders
function _dwselDecorate() {
  var b = document.getElementById('btn-plan-mosaic');
  if (!b || document.getElementById('btn-dwsel-add')) return;
  var add = document.createElement('button');
  add.id = 'btn-dwsel-add'; add.type = 'button'; add.className = 'btn-plan-mosaic';
  add.style.marginLeft = '8px'; add.style.whiteSpace = 'nowrap';
  add.title = 'Add this object to your own list to program on the Dwarf (' + DWSEL_MAX + ' max)';
  add.innerHTML = '&#65291; Dwarf list';
  add.addEventListener('click', _dwselAddCurrent);
  b.insertAdjacentElement('afterend', add);
}

/* ---------- floating chip + list panel ---------- */
function _dwselRenderChip() {
  var list = _dwselLoad(), chip = document.getElementById('dwsel-chip');
  if (!chip) {
    chip = document.createElement('button');
    chip.id = 'dwsel-chip'; chip.type = 'button';
    chip.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:2200;background:var(--bg2,#111a2b);color:var(--teal,#30c8c0);' +
      'border:1px solid var(--teal,#30c8c0);border-radius:20px;padding:8px 14px;font-size:13px;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.4)';
    chip.addEventListener('click', _dwselTogglePanel);
    document.body.appendChild(chip);
  }
  chip.style.display = list.length ? '' : 'none';
  chip.textContent = '📡 Dwarf list (' + list.length + '/' + DWSEL_MAX + ')';
  var panel = document.getElementById('dwsel-panel');
  if (panel && panel.style.display !== 'none') _dwselRenderPanel();
  if (!list.length && panel) panel.style.display = 'none';
}

function _dwselTogglePanel() {
  var panel = document.getElementById('dwsel-panel');
  if (panel && panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  _dwselRenderPanel();
}

function _dwselRenderPanel() {
  var panel = document.getElementById('dwsel-panel');
  if (!panel) {
    panel = document.createElement('div'); panel.id = 'dwsel-panel';
    panel.style.cssText = 'position:fixed;left:16px;bottom:62px;z-index:2200;width:320px;max-width:calc(100vw - 32px);' +
      'background:var(--bg2,#111a2b);color:var(--text,#e6eefb);border:1px solid var(--border2,#33415c);border-radius:10px;' +
      'padding:12px;font-size:13px;box-shadow:0 4px 18px rgba(0,0,0,.5)';
    panel.addEventListener('click', function (e) {
      var rm = e.target.closest ? e.target.closest('[data-dwsel-rm]') : null;
      if (rm) { _dwselSave(_dwselLoad().filter(function (o) { return o.id !== rm.getAttribute('data-dwsel-rm'); })); return; }
      if (e.target.id === 'dwsel-clear') { _dwselSave([]); return; }
      if (e.target.id === 'dwsel-program') _dwselProgram();
    });
    document.body.appendChild(panel);
  }
  var list = _dwselLoad(), h = '<div style="font-weight:650;margin-bottom:8px">📡 My Dwarf list</div>';
  list.forEach(function (o) {
    h += '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-top:1px solid var(--border,#22304a)">' +
      '<span style="flex:1">' + _dwselEsc(o.name) + (o.name !== o.id ? ' <span style="color:var(--text3,#7c8aa5)">' + _dwselEsc(o.id) + '</span>' : '') + '</span>' +
      '<button type="button" data-dwsel-rm="' + _dwselEsc(o.id) + '" title="Remove" style="background:none;border:0;color:var(--text2,#a8b3c7);cursor:pointer;font-size:14px">&#10005;</button></div>';
  });
  h += '<div style="display:flex;gap:8px;margin-top:10px">' +
    '<button type="button" id="dwsel-program" class="btn-plan-mosaic" style="margin-top:0;flex:1">Program to the Dwarf</button>' +
    '<button type="button" id="dwsel-clear" class="btn-plan-mosaic" style="margin-top:0">Clear</button></div>' +
    '<div style="font-size:11px;color:var(--text3,#7c8aa5);margin-top:8px">Tonight at the active site, ' + _dwselEsc(_dwselRig().key) +
    ' rig: each object\'s usable window, filter and exposure as in Best of Tonight.</div>';
  panel.innerHTML = h;
  panel.style.display = '';
}

/* ---------- build the plans and open the Dwarf panel ---------- */
function _dwselRig() {
  var configs = (typeof RIG_GROUPS !== 'undefined') ? RIG_GROUPS.flatMap(function (g) { return g.configs || []; }) : [];
  var key = (typeof filterRig === 'string' && (filterRig === 'D3' || filterRig === 'DMINI')) ? filterRig : 'D3';
  return configs.find(function (c) { return c && c.key === key; }) || { key: key };
}

function _dwselNight(site) {
  // The night's date: today, or yesterday before noon (still last night);
  // anchored at local noon as the Best-of-Tonight plan does (see its
  // _planDateForNightWindow fix), so the right night is picked whatever
  // the site's longitude.
  var now = new Date(), d = new Date(now);
  if (now.getHours() < 12) d.setDate(d.getDate() - 1);
  var iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  var anchor = new Date(iso + 'T12:00:00');
  var nightDef = (typeof getNightDef === 'function' && typeof getActiveLocationId === 'function') ? getNightDef(getActiveLocationId()) : 'astronomical';
  var date = (typeof pickerSampleDate === 'function') ? pickerSampleDate(iso, null, site, nightDef) : anchor;
  var win = (typeof astroNightWindow === 'function') ? astroNightWindow(anchor, site.lat, site.lon || 0) : null;
  return { date: date, window: win };
}

function _dwselProgram() {
  var list = _dwselLoad();
  if (!list.length) return;
  if (typeof window.openDwarfProgramPanel !== 'function' || typeof _planBuildPlan !== 'function') {
    _dwselToast('The Dwarf programming panel is not available on this page.'); return;
  }
  var site = (typeof getActiveLocation === 'function') ? getActiveLocation() : null;
  if (!site || typeof site.lat !== 'number' || site.needsSetup) { _dwselToast('Set your observing site first.'); return; }
  var night = _dwselNight(site);
  if (!night.window || !night.window.startUTC) { _dwselToast('No dark window tonight at this site.'); return; }
  var rig = _dwselRig(), lat = site.lat, lon = site.lon || 0, plans = [], skipped = [];
  list.forEach(function (o) {
    var t = (typeof ATLAS_FULL !== 'undefined') ? ATLAS_FULL.find(function (a) { return a[0] === o.id; }) : null;
    var ra = t ? t[2] : o.ra, dec = t ? t[3] : o.dec;
    if (typeof ra !== 'number' || typeof dec !== 'number') { skipped.push(o.name); return; }
    var usable = _planComputeUsableHours(ra, dec, lat, lon, night.window);
    if (!usable || !usable.hours) { skipped.push(o.name); return; }
    var peak = (typeof peakAltitudeTonight === 'function') ? peakAltitudeTonight(ra, dec, lat, lon, night.window, null) : null;
    var c = {
      id: o.id, type: t ? t[1] : '', ra: ra, dec: dec, mag: t ? t[4] : null, size: t ? t[5] : null,
      con: t ? t[6] : '', cname: t ? t[7] : o.name, messier: t ? t[8] : '', token: t ? t[10] : undefined,
      peakAlt: peak ? peak.peakAlt : null, peakTime: peak ? peak.peakTimeUTC : null,
      usableHours: usable.hours, usableStart: usable.startUTC || night.window.startUTC, usableEnd: usable.endUTC || night.window.endUTC
    };
    var p = _planBuildPlan(c, rig, site, night.date, plans.length);
    p.ra = ra; p.dec = dec;
    plans.push(p);
  });
  if (skipped.length) _dwselToast('Not usable tonight at this site: ' + skipped.join(', '));
  if (!plans.length) return;
  var panel = document.getElementById('dwsel-panel'); if (panel) panel.style.display = 'none';
  window.openDwarfProgramPanel(plans, { title: 'My Dwarf list', siteName: site.name || 'this site', siteId: site.id });
}

/* ---------- start ---------- */
(function () {
  function start() {
    _dwselRenderChip();
    _dwselDecorate();
    new MutationObserver(_dwselDecorate).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
