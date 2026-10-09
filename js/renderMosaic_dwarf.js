/* =====================================================================
   Mosaic Planner - DWARF version (port of the ASIAIR renderMosaic)

   Replaces:  ASIAIR rig list  ->  Dwarf devices (GET /api/dwarfs) + Wide/Tele FOV per model
              ASIAIR .txt plan ->  schedule (visibility + time slots) + POST /api/program
              rotation / pane angle -> removed (the Dwarf has no camera rotator)
              added: EQ mode (+10 pts overlap in Alt-Az), capture settings, site, start time

   Reused as-is from catalog.html:
     _mosaicTarget(), _fmtRAsp(), _fmtDecsp(), _mosaicDrawPreview(), getActiveLocation(),
     window._lastImagingRec  (K-Photon default exposure)
   Globals expected: var mosaicPlan, var _mosaicBigGridWarn (as before)

   Integration (Oct 2026): catalog.html keeps its ASIAIR planner. The rail's
   "Planner" choice (ASIAIR rigs / Dwarf) is remembered in localStorage
   (dso_mosaic_mode); catalog.html's renderMosaic() hands over to
   renderMosaicDwarf() in Dwarf mode. Both share mosaicPlan (rows, cols,
   overlap, exposure); the Dwarf-only fields are also kept in mosaicPlan_dwarf.
   ===================================================================== */

var DWARF_FOV = {
  wide: {
    'Dwarf 3':    { h: 44.1, v: 24.8 },
    'Dwarf Mini': { h: 43.6, v: 24.5 },
    'default':    { h: 44.0, v: 24.6 }
  },
  // Tele = sensor size / focal length (Dwarf II: IMX415 3840x2160 @1.45um, 100mm; Dwarf 3: IMX678 3856x2180 @2um, 150mm;
  // Mini: IMX662 1920x1080 @2.9um, 150mm). Mini's 2.13x1.20 is computed - compare with your own plate-solved frames.
  tele: {
    'Dwarf II':   { h: 3.19, v: 1.79 },
    'Dwarf 3':    { h: 2.94, v: 1.66 },
    'Dwarf Mini': { h: 2.13, v: 1.20 },
    'default':    { h: 2.94, v: 1.66 }
  }
};
var UNSUPPORTED_WIDE_MODELS = ['Dwarf II'];   // Wide uses other protocol IDs on the Dwarf II (Tele is fine)
var DW_AUTOFOCUS_BUFFER_S = 90;               // extra time for tiles that run autofocus
var DW_MOSAIC_IN_SETUP_CAMERA = true;         // doMosaic/framing*/mosaic_count live ONLY in payload.setup_camera (confirmed)
var DW_TILE_BUFFER_S = 60;                    // goto / settle per tile
var _DW_DEG = Math.PI / 180;

/* Planner mode: 'asiair' (catalog.html's own planner) or 'dwarf' */
function _mosaicMode() {
  try { return localStorage.getItem('dso_mosaic_mode') === 'dwarf' ? 'dwarf' : 'asiair'; } catch (e) { return 'asiair'; }
}
function _setMosaicMode(mode) {
  try { localStorage.setItem('dso_mosaic_mode', mode === 'dwarf' ? 'dwarf' : 'asiair'); } catch (e) {}
}
// "Planner" card shown at the top of both rails
function _mosaicModeCard() {
  var m = _mosaicMode();
  return '<div class="mcard"><h4>Planner</h4><select id="m-mode">' +
    '<option value="asiair"' + (m === 'asiair' ? ' selected' : '') + '>ASIAIR rigs (plan export)</option>' +
    '<option value="dwarf"' + (m === 'dwarf' ? ' selected' : '') + '>Dwarf 3 / Dwarf Mini (Astro Dwarf Session)</option>' +
    '</select></div>';
}

/* Altitude / azimuth (degrees) of RA (hours) / Dec at lat / lon (E+) and date */
function _dwAltAz(raH, decDeg, latDeg, lonDeg, date) {
  var d = date.getTime() / 86400000 + 2440587.5 - 2451545.0;
  var lst = ((280.46061837 + 360.98564736629 * d + lonDeg) % 360 + 360) % 360;
  var ha = (lst - raH * 15) * _DW_DEG, dec = decDeg * _DW_DEG, lat = latDeg * _DW_DEG;
  var sinAlt = Math.sin(dec) * Math.sin(lat) + Math.cos(dec) * Math.cos(lat) * Math.cos(ha);
  var alt = Math.asin(Math.max(-1, Math.min(1, sinAlt)));
  var az = Math.atan2(-Math.sin(ha) * Math.cos(dec), Math.sin(dec) * Math.cos(lat) - Math.cos(dec) * Math.sin(lat) * Math.cos(ha));
  return { alt: alt / _DW_DEG, az: ((az / _DW_DEG) % 360 + 360) % 360 };
}

/* Tangent-plane offsets (degrees, E / N) of a pane from the target, as
   catalog.html's _mosaicDrawPreview() expects them (xi / eta) */
function _dwOffsets(panes, tgt) {
  var cosD = Math.max(0.05, Math.cos(tgt.dec * _DW_DEG));
  return panes.map(function (p) {
    var dRa = (p.raH - tgt.raH) * 15; if (dRa > 180) dRa -= 360; if (dRa < -180) dRa += 360;
    return Object.assign({}, p, { xi: dRa * cosD, eta: p.dec - tgt.dec });
  });
}

var _dwAll = null;          // all devices from the server (null = not loaded yet)
var _dwDevices = null;      // usable for the selected camera
var _dwExcluded = 0;
var _dwLoading = false;
var _dwStatus = '';         // send status line
var _dwSched = [];          // last computed schedule
var _dwBound = false;
var _dwNight = null;        // dark window used by the last schedule

/* ---------- helpers ---------- */
function _dwFov(model, cam) { var t = DWARF_FOV[cam] || DWARF_FOV.wide; return t[model] || t['default']; }

// Devices usable for the selected camera (Dwarf II only excluded for Wide) + keeps a valid selection
function _dwRefreshList() {
  if (!_dwAll) { _dwDevices = null; return; }
  var wide = mosaicPlan.camera !== 'tele';
  _dwExcluded = wide ? _dwAll.filter(function (d) { return UNSUPPORTED_WIDE_MODELS.indexOf(d.model) >= 0; }).length : 0;
  _dwDevices = _dwAll.filter(function (d) { return !wide || UNSUPPORTED_WIDE_MODELS.indexOf(d.model) < 0; });
  if (_dwDevices.length && !_dwDevices.some(function (d) { return d.dwarfUid === mosaicPlan.dwarfUid; }))
    mosaicPlan.dwarfUid = _dwDevices[0].dwarfUid;
}

function _dwApiBase() {
  var u = (mosaicPlan && mosaicPlan.serverUrl || '').trim().replace(/\/+$/, '');
  if (!u && /^https?:$/.test(location.protocol)) u = location.origin;
  return u;
}

function _dwSavePlan() {
  try { localStorage.setItem('mosaicPlan_dwarf', JSON.stringify(mosaicPlan)); } catch (e) {}
}

function _dwLoadDevices() {
  if (_dwLoading) return;
  _dwLoading = true;
  fetch(_dwApiBase() + '/api/dwarfs').then(function (r) { return r.json(); }).then(function (data) {
    _dwAll = data.devices || [];
  }).catch(function () { _dwAll = []; })
    .then(function () { _dwLoading = false; renderMosaic(); });
}

function _dwRig() {               // { fovW, fovH, model, uid }
  if (!_dwDevices) return null;
  var d = _dwDevices.filter(function (x) { return x.dwarfUid === mosaicPlan.dwarfUid; })[0];
  if (!d) return null;
  var f = _dwFov(d.model, mosaicPlan.camera);
  return { fovW: f.h, fovH: f.v, model: d.model, uid: d.dwarfUid };
}

/* Native Dwarf mosaic (Tele only). framingX/Y = size of the final capture in % of ONE tele frame per axis
   (100 = single frame on that axis = no mosaic along it, 180 = max = 2 panels, 10% overlap between panels).
   Panels = (X>100 ? 2 : 1) x (Y>100 ? 2 : 1), so 1, 2 or 4. mosaic_count = images PER panel. */
function _dwNative(P) {
  var on = P.camera === 'tele' && !!P.native;
  var fx = Math.min(180, Math.max(100, Math.round(+P.framingX || 100))), fy = Math.min(180, Math.max(100, Math.round(+P.framingY || 100)));
  var nx = on && fx > 100 ? 2 : 1, ny = on && fy > 100 ? 2 : 1;
  return { on: on, fx: fx, fy: fy, nx: nx, ny: ny, n: nx * ny };
}
// images per panel/tile: count mode = as entered; duration mode = ceil(time/exp) (x1.2 + endTime cut-off for plain tiles only)
function _dwImgCount(P, exp, nat) {
  var n = P.durationMode !== 'duration' ? +P.count : (exp ? Math.ceil(P.tileMin * 60 / exp * (nat.on ? 1 : 1.2)) : 0);
  return nat.on ? Math.min(249, n) : n;   // the Dwarf editor caps mosaic_count at 249 images per panel
}
// sub-panel centres of a native tile, for the preview (2 panels along an axis sit at +/-(framing-100)/200 of one frame)
function _dwPanels(t, fov, nat) {
  var out = [], dy = fov.v * (nat.fy - 100) / 200, dx = fov.h * (nat.fx - 100) / 200, cosD = Math.max(0.05, Math.cos(t.dec * _DW_DEG));
  for (var iy = 0; iy < nat.ny; iy++) for (var ix = 0; ix < nat.nx; ix++) {
    out.push(Object.assign({}, t, { dec: t.dec + (nat.ny === 2 ? (iy ? dy : -dy) : 0),
      raH: (((t.raH + (nat.nx === 2 ? (ix ? dx : -dx) / cosD / 15 : 0)) % 24) + 24) % 24, angle: 0 }));
  }
  return out;
}

/* Grid (same maths as generateGrid in the Milky Way planner) */
function _dwGrid(tgt, fov, rows, cols, overlapPct) {
  var ov = overlapPct / 100, stepH = fov.h * (1 - ov), stepV = fov.v * (1 - ov), out = [], n = 0;
  for (var r = 0; r < rows; r++) {
    var dec = tgt.dec + (r - (rows - 1) / 2) * stepV;
    var cosDec = Math.max(0.05, Math.cos(dec * _DW_DEG));
    for (var c = 0; c < cols; c++) {
      var ra = tgt.raH + ((c - (cols - 1) / 2) * stepH / cosDec) / 15;
      out.push({ i: ++n, name: (rows * cols > 1 ? tgt.name + ' R' + (r + 1) + 'C' + (c + 1) : tgt.name),
        raH: ((ra % 24) + 24) % 24, dec: dec, angle: 0, row: r, col: c });
    }
  }
  return out;
}

/* The night to plan: the site's dark window (catalog.html's astroNightWindow,
   astronomical darkness, else the darkest level available) of the night the
   start time belongs to - a start before noon is still the previous night.
   Anchored at local noon, as the Best-of-Tonight plan does. null: no dark
   window at all (polar day) or the function is missing. */
function _dwNightWindow(startDate, lat, lon) {
  if (typeof astroNightWindow !== 'function') return null;
  var d = new Date(startDate);
  if (d.getHours() < 12) d.setDate(d.getDate() - 1);
  var anchor = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12, 0, 0);
  try { return astroNightWindow(anchor, lat, lon); } catch (e) { return null; }
}

/* Greedy scheduler (same logic as scheduleTiles in the Milky Way planner),
   kept inside the night (user-reported Oct 2026: with altitude as the only
   test, a target only high in daytime got a tile at 08:45 the next morning) */
function _dwSchedule(tiles, lat, lon, startDate, minAlt, durFn, night) {
  var stepMs = 5 * 60000;
  var from = night ? Math.max(startDate.getTime(), night.startUTC.getTime()) : startDate.getTime();
  var deadline = night ? night.endUTC.getTime() : startDate.getTime() + 12 * 3600000;
  var cursor = new Date(from), res = [];
  tiles.forEach(function (t, i) {
    var dur = durFn(t), found = null, probe = new Date(cursor);
    while (probe.getTime() < deadline) {
      var a = _dwAltAz(t.raH, t.dec, lat, lon, probe).alt;
      var end = new Date(probe.getTime() + dur * 1000);
      if (end.getTime() > deadline) break;   // would end after dawn
      if (a >= minAlt) {
        if (_dwAltAz(t.raH, t.dec, lat, lon, end).alt >= minAlt) { found = { start: new Date(probe), end: end, alt: a }; break; }
      }
      probe = new Date(probe.getTime() + stepMs);
    }
    if (found) { res.push(Object.assign({}, t, { ok: true, start: found.start, end: found.end, alt: found.alt }));
      cursor = new Date(found.end.getTime() + 30000); }
    else res.push(Object.assign({}, t, { ok: false }));
  });
  return res;
}

function _dwPad(n) { return String(n).padStart(2, '0'); }
function _dwFmtT(d) { return _dwPad(d.getDate()) + '/' + _dwPad(d.getMonth() + 1) + ' ' + _dwPad(d.getHours()) + ':' + _dwPad(d.getMinutes()); }

/* ---------- main render ---------- */
function renderMosaicDwarf() {
  var rail = document.getElementById('mosaic-rail'), stage = document.getElementById('mosaic-stage');
  if (!rail || !stage) return;
  var tgt = _mosaicTarget();
  var chip = document.getElementById('mosaic-target-chip');
  if (chip) chip.innerHTML = tgt ? ('&#127919; ' + tgt.name) : 'No target selected';

  var _saved = null; try { _saved = JSON.parse(localStorage.getItem('mosaicPlan_dwarf')); } catch (e) {}
  var D = { camera: 'wide', dwarfUid: '', rows: 2, cols: 3, overlapPct: 15, eqMode: false, expSec: null, expTarget: null, gain: 80,
    durationMode: 'count', count: 60, tileMin: 60, autofocusFirstOnly: true, lat: '', lon: '', startTime: '21:00:00',
    minAlt: 25, serverUrl: '', bigAck: false, native: false, framingX: 180, framingY: 180 };
  // Dwarf fields kept from the last Dwarf plan; rows / cols / overlap / exposure shared with the ASIAIR planner
  mosaicPlan = Object.assign({}, D, _saved || {}, mosaicPlan || {});
  if (mosaicPlan.lat === '' || mosaicPlan.lon === '') {   // site: the catalogue's active location by default
    var _loc = (typeof getActiveLocation === 'function') ? getActiveLocation() : null;
    if (_loc && !_loc.needsSetup && isFinite(_loc.lat) && isFinite(_loc.lon)) { mosaicPlan.lat = String(_loc.lat); mosaicPlan.lon = String(_loc.lon); }
  }
  if (_dwAll === null && !_dwLoading) _dwLoadDevices();
  _dwRefreshList();

  /* ---- rail ---- */
  var devOpts = '';
  (_dwDevices || []).forEach(function (d) {
    devOpts += '<option value="' + d.dwarfUid + '"' + (d.dwarfUid === mosaicPlan.dwarfUid ? ' selected' : '') + '>' +
      (d.name || d.dwarfUid) + ' (' + [d.model, d.ip, d.connected ? 'connected' : 'disconnected'].filter(Boolean).join(' · ') + ')</option>';
  });
  if (!devOpts) devOpts = '<option value="">' + (_dwDevices === null ? 'Loading…' : 'No compatible device') + '</option>';
  var rig = _dwRig();
  var P = mosaicPlan, rh = '';

  rh += _mosaicModeCard();
  rh += '<div class="mcard"><h4>Target</h4>';
  if (tgt) rh += '<div class="m-tgt-name">' + tgt.name + '</div><div class="m-tgt-sub">' + (tgt.id || '') + '</div>' +
    '<div class="m-tgt-coords"><span>RA ' + _fmtRAsp(tgt.raH) + '</span><span>Dec ' + _fmtDecsp(tgt.dec) + '</span></div>';
  else rh += '<div class="m-tgt-sub">Select an object in the catalogue, then open the Mosaic Planner.</div>';
  rh += '</div>';

  rh += '<div class="mcard"><h4>Dwarf</h4>' +
    '<label class="fld">astro_dwarf_session server</label><input type="text" id="m-server" value="' + P.serverUrl + '" placeholder="http://host:port">' +
    '<label class="fld">Camera</label><select id="m-cam"><option value="wide"' + (P.camera === 'wide' ? ' selected' : '') + '>Wide</option>' +
    '<option value="tele"' + (P.camera === 'tele' ? ' selected' : '') + '>Tele</option></select>' +
    '<label class="fld">Device</label><select id="m-dwarf">' + devOpts + '</select>' +
    '<div class="m-rig-fov" id="m-rig-fov">' + (rig ? (P.camera === 'tele' ? 'Tele' : 'Wide') + ' FOV per pane <b>' + rig.fovW.toFixed(P.camera === 'tele' ? 2 : 1) + '&deg; &times; ' + rig.fovH.toFixed(P.camera === 'tele' ? 2 : 1) + '&deg;</b>' : '') +
    (_dwExcluded ? '<br>' + _dwExcluded + ' Dwarf II hidden (Wide not supported - use Tele).' : '') + '</div></div>';

  rh += '<div class="mcard"><h4>Mosaic grid</h4>' +
    '<div class="m-grid-row"><div><label class="fld">Columns (E&ndash;W)</label><input type="number" id="m-cols" min="1" max="999" value="' + P.cols + '"></div>' +
    '<div><label class="fld">Rows (N&ndash;S)</label><input type="number" id="m-rows" min="1" max="999" value="' + P.rows + '"></div></div>' +
    ((_mosaicBigGridWarn && !P.bigAck) ? '<div class="m-bigwarn">&#9888; Grids over 50&times;50 make a very long plan and can be slow. <button id="m-allowbig" class="m-allowbig-btn">Allow large grids</button></div>' : '') +
    '<div style="height:10px"></div>' +
    '<label class="fld">Overlap %</label><input type="number" id="m-overlap" min="0" max="60" step="5" value="' + P.overlapPct + '">' +
    '<label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-size:12px;color:var(--text2);cursor:pointer">' +
    '<input type="checkbox" id="m-eq"' + (P.eqMode ? ' checked' : '') + '> Dwarf in EQ mode</label>' +
    '<div style="font-size:10.5px;color:var(--text3);margin-top:4px;font-family:var(--mono,monospace)">' +
    (P.eqMode ? 'EQ tracking: overlap used as entered.' : 'Alt-Az: +10 pts overlap for field rotation.') + '</div>' +
    (P.camera === 'tele' ? ('<label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-size:12px;color:var(--text2);cursor:pointer">' +
      '<input type="checkbox" id="m-native"' + (P.native ? ' checked' : '') + '> Mosaic</label>' +
      (P.native ? ('<div class="m-grid-row"><div><label class="fld">Framing X (1.0&ndash;1.8)</label><input type="number" id="m-fx" min="1" max="1.8" step="0.1" value="' + (P.framingX / 100).toFixed(1) + '"></div>' +
        '<div><label class="fld">Framing Y (1.0&ndash;1.8)</label><input type="number" id="m-fy" min="1" max="1.8" step="0.1" value="' + (P.framingY / 100).toFixed(1) + '"></div></div>' +
        '<div style="font-size:10.5px;color:var(--text3);margin-top:4px;font-family:var(--mono,monospace)">Value as shown in the official app: 1.0 = single frame on that axis, 1.8 = max (2 panels, 10% overlap). Columns/Rows below then count mosaics.</div>') : '')) : '') +
    '</div>';

  // exposure default = K-Photon sub length from the detail pane (as before)
  var _ptr = (window._lastImagingRec && tgt && window._lastImagingRec.objId === tgt.id) ? window._lastImagingRec : null;
  if (tgt && P.expTarget !== tgt.id) { P.expSec = _ptr ? _ptr.subSec : (P.expSec || 15); P.expTarget = tgt.id; }
  var expSrc = _ptr ? ' &middot; K-Photon' + (_ptr.filter ? ' / ' + _ptr.filter : '') : ' &middot; set manually';
  rh += '<div class="mcard"><h4>Capture</h4>' +
    '<div class="m-grid-row"><div><label class="fld">Exposure (s)<span class="m-exp-src">' + expSrc + '</span></label><input type="number" id="m-exp" min="1" step="1" value="' + (P.expSec == null ? '' : P.expSec) + '"></div>' +
    '<div><label class="fld">Gain</label><input type="number" id="m-gain" min="0" step="1" value="' + P.gain + '"></div></div>' +
    '<label class="fld">Per-tile mode</label><select id="m-dmode"><option value="count"' + (P.durationMode === 'count' ? ' selected' : '') + '>Fixed image count</option>' +
    '<option value="duration"' + (P.durationMode === 'duration' ? ' selected' : '') + '>Fixed duration per tile</option></select>' +
    (P.durationMode === 'count'
      ? '<label class="fld">Images per ' + (_dwNative(P).on ? 'panel' : 'tile') + '</label><input type="number" id="m-count" min="1" value="' + P.count + '">'
      : '<label class="fld">Minutes per ' + (_dwNative(P).on ? 'panel' : 'tile') + '</label><input type="number" id="m-tilemin" min="1" value="' + P.tileMin + '">') +
    '<label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-size:12px;color:var(--text2);cursor:pointer">' +
    '<input type="checkbox" id="m-af"' + (P.autofocusFirstOnly ? ' checked' : '') + '> Autofocus on first tile only</label></div>';

  rh += '<div class="mcard"><h4>Schedule</h4>' +
    '<div class="m-grid-row"><div><label class="fld">Latitude &deg;</label><input type="number" id="m-lat" step="0.0001" value="' + P.lat + '"></div>' +
    '<div><label class="fld">Longitude &deg; (E+)</label><input type="number" id="m-lon" step="0.0001" value="' + P.lon + '"></div></div>' +
    '<div class="m-grid-row"><div><label class="fld">Start time</label><input type="time" id="m-start" step="1" value="' + P.startTime + '"></div>' +
    '<div><label class="fld">Min altitude &deg;</label><input type="number" id="m-minalt" min="0" max="89" value="' + P.minAlt + '"></div></div></div>';

  rh += '<div class="mcard m-summary"><h4>Summary</h4>' +
    '<div class="srow"><span class="k">Tiles</span><span class="v big" id="m-s-panes">&mdash;</span></div>' +
    '<div class="srow"><span class="k">Total field</span><span class="v" id="m-s-field">&mdash;</span></div>' +
    '<div class="srow"><span class="k">Overlap used</span><span class="v" id="m-s-ov">&mdash;</span></div>' +
    '<div class="srow"><span class="k">Total integration</span><span class="v" id="m-s-time">&mdash;</span></div>' +
    '<div class="srow"><span class="k">Schedulable</span><span class="v" id="m-s-ok">&mdash;</span></div></div>';
  rail.innerHTML = rh;

  /* ---- stage ---- */
  if (!tgt || !rig) {
    stage.innerHTML = '<div class="mcard"><h4>Dwarf Mosaic Program</h4><div class="m-tgt-sub">' +
      (!tgt ? 'Pick a target to generate a program.' : 'Pick a Dwarf (server URL above) to generate a program.') + '</div></div>';
    _dwBind(); return;
  }

  var fov = { h: rig.fovW, v: rig.fovH };
  var nat = _dwNative(P);
  var tileFov = nat.on ? { h: fov.h * nat.fx / 100, v: fov.v * nat.fy / 100 } : fov;   // a native mosaic is one big "tile"
  var effOv = P.eqMode ? P.overlapPct : P.overlapPct + 10;
  var tiles = _dwGrid(tgt, tileFov, P.rows, P.cols, effOv);
  var exp = (P.expSec > 0) ? +P.expSec : null;
  var count = _dwImgCount(P, exp, nat);
  var perPanelSec = P.durationMode === 'duration' ? P.tileMin * 60 : (exp || 0) * count;
  var baseDur = nat.n * (perPanelSec + DW_TILE_BUFFER_S);
  var durFn = function (t) { return baseDur + ((P.autofocusFirstOnly ? (t.row === 0 && t.col === 0) : true) ? DW_AUTOFOCUS_BUFFER_S : 0); };

  var lat = parseFloat(P.lat), lon = parseFloat(P.lon), hasSite = isFinite(lat) && isFinite(lon) && exp;
  var startDate = null;
  if (hasSite) {
    var ts = (P.startTime || '00:00:00').split(':').map(Number), now = new Date();
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), ts[0], ts[1], ts[2] || 0);
    if (startDate < now) startDate.setDate(startDate.getDate() + 1);   // rolls to tomorrow - shown in the header
    var night = _dwNightWindow(startDate, lat, lon);
    _dwNight = night;
    _dwSched = night ? _dwSchedule(tiles, lat, lon, startDate, +P.minAlt, durFn, night)
                     : tiles.map(function (t) { return Object.assign({}, t, { ok: false }); });
    if (!P.eqMode) _dwSched.forEach(function (t) { if (t.ok && t.alt > 80) t.nearZenith = true; });
  } else { _dwSched = tiles.map(function (t) { return Object.assign({}, t, { ok: false, pending: true }); }); }

  var setT = function (id, v) { var e = document.getElementById(id); if (e) e.textContent = v; };
  var fW = P.cols * tileFov.h - (P.cols - 1) * tileFov.h * effOv / 100, fH = P.rows * tileFov.v - (P.rows - 1) * tileFov.v * effOv / 100;
  var okN = _dwSched.filter(function (t) { return t.ok; }).length;
  setT('m-s-panes', nat.on ? tiles.length + ' × ' + nat.n + ' panel' + (nat.n > 1 ? 's' : '') : tiles.length); setT('m-s-field', fW.toFixed(P.camera === 'tele' ? 2 : 1) + '° × ' + fH.toFixed(P.camera === 'tele' ? 2 : 1) + '°');
  setT('m-s-ov', effOv + '%' + (P.eqMode ? '' : ' (Alt-Az)') + (nat.on ? ' · panels 10%' : ''));
  if (exp) { var secs = tiles.length * nat.n * perPanelSec, mm = Math.round(secs / 60);
    setT('m-s-time', mm >= 60 ? Math.floor(mm / 60) + 'h ' + (mm % 60) + 'm' : mm + 'm'); } else setT('m-s-time', 'set exposure');
  setT('m-s-ok', hasSite ? okN + ' / ' + tiles.length : 'set site');

  var rows = '';
  _dwSched.forEach(function (t) {
    rows += '<tr' + (t.ok || t.pending ? '' : ' class="unschedulable"') + '><td class="lbl">' + (t.name === tgt.name ? '1' : t.name.replace(tgt.name + ' ', '')) + '</td>' +
      '<td class="num">' + _fmtRAsp(t.raH) + '</td><td class="num">' + _fmtDecsp(t.dec) + '</td>' +
      '<td class="num">' + (t.ok ? t.alt.toFixed(0) + '&deg;' : '&mdash;') + '</td>' +
      '<td class="num">' + (t.ok ? _dwFmtT(t.start) : (t.pending ? '&mdash;' : 'No slot tonight')) + (t.nearZenith ? ' &#9888;' : '') + '</td></tr>';
  });
  var head = startDate ? (_dwNight ? 'Night: ' + _dwFmtT(new Date(Math.max(startDate.getTime(), _dwNight.startUTC.getTime()))) + ' &rarr; ' +
    _dwPad(_dwNight.endUTC.getHours()) + ':' + _dwPad(_dwNight.endUTC.getMinutes()) + ' &middot; ' : 'No dark window tonight &middot; ') : '';
  stage.innerHTML = '<div class="m-export"><div class="m-export-head"><h3><span class="ic">&#11015;</span> Dwarf Mosaic Program</h3>' +
    '<span class="m-cnt">' + head + P.cols + '&times;' + P.rows + '</span>' +
    '<div class="m-actions"><button class="mbtn primary" id="m-send"' + (okN ? '' : ' disabled') + '>Send ' + okN + (nat.on ? ' mosaic(s)' : ' tile(s)') + ' to Dwarf</button></div></div>' +
    '<div class="m-export-body"><div class="m-preview-col"><div class="m-preview"><svg id="m-preview" width="360" height="240" viewBox="0 0 360 240"></svg>' +
    '<div class="m-prev-cap" id="m-prev-cap">Target shape to scale &middot; teal = panes</div></div>' +
    '<div class="m-foot-note" id="m-status">' + (_dwStatus || '<b>How to use:</b> set your site, generate, then <span class="step">Send</span>. Arm the device on the Programs page so the schedule starts automatically.') + '</div></div>' +
    '<div class="m-plan-col"><div class="m-plan-wrap"><table class="m-plan"><thead><tr><th>' + (nat.on ? 'Mosaic' : 'Tile') + '</th><th>RA</th><th>DEC</th><th>Alt</th><th>Start</th></tr></thead><tbody>' + rows + '</tbody></table></div></div></div></div>';
  var prevPanes = nat.on ? [].concat.apply([], _dwSched.map(function (t) { return _dwPanels(t, fov, nat); })) : _dwSched;
  var _rot = mosaicPlan.rotDeg; mosaicPlan.rotDeg = 0;   // the Dwarf has no camera rotation
  try { _mosaicDrawPreview(tgt, { fovW: fov.h, fovH: fov.v }, _dwOffsets(prevPanes, tgt)); } finally { mosaicPlan.rotDeg = _rot; }
  _dwBind();
}

/* ---------- events (delegated, bound once on the rail; 'change' only so typing isn't interrupted) ---------- */
function _dwBind() {
  if (_dwBound) return;
  var rail = document.getElementById('mosaic-rail'), stage = document.getElementById('mosaic-stage');
  if (!rail || !stage) return;
  _dwBound = true;
  var num = function (v, d) { var n = parseFloat(v); return isFinite(n) ? n : d; };
  rail.addEventListener('change', function (e) {
    if (_mosaicMode() !== 'dwarf') return;   // the ASIAIR planner handles its own controls
    var id = e.target.id, v = e.target.value, P = mosaicPlan;
    if (id === 'm-server') { P.serverUrl = v.trim().replace(/\/+$/, ''); _dwAll = null; }
    else if (id === 'm-cam') P.camera = v;
    else if (id === 'm-dwarf') P.dwarfUid = v;
    else if (id === 'm-cols') P.cols = Math.max(1, parseInt(v, 10) || 1);
    else if (id === 'm-rows') P.rows = Math.max(1, parseInt(v, 10) || 1);
    else if (id === 'm-overlap') P.overlapPct = Math.min(60, Math.max(0, num(v, 15)));
    else if (id === 'm-eq') P.eqMode = e.target.checked;
    else if (id === 'm-native') P.native = e.target.checked;
    else if (id === 'm-fx') P.framingX = Math.min(180, Math.max(100, Math.round(num(v, 1.8) * 100)));
    else if (id === 'm-fy') P.framingY = Math.min(180, Math.max(100, Math.round(num(v, 1.8) * 100)));
    else if (id === 'm-exp') P.expSec = num(v, null);
    else if (id === 'm-gain') P.gain = num(v, 80);
    else if (id === 'm-dmode') P.durationMode = v;
    else if (id === 'm-count') P.count = Math.max(1, parseInt(v, 10) || 1);
    else if (id === 'm-tilemin') P.tileMin = Math.max(1, num(v, 60));
    else if (id === 'm-af') P.autofocusFirstOnly = e.target.checked;
    else if (id === 'm-lat') P.lat = v;
    else if (id === 'm-lon') P.lon = v;
    else if (id === 'm-start') P.startTime = v;
    else if (id === 'm-minalt') P.minAlt = num(v, 25);
    else return;
    _dwStatus = ''; _dwSavePlan(); renderMosaic();
  });
  rail.addEventListener('click', function (e) {
    if (_mosaicMode() !== 'dwarf') return;
    if (e.target.id === 'm-allowbig') { mosaicPlan.bigAck = true; _dwSavePlan(); renderMosaic(); }
  });
  stage.addEventListener('click', function (e) { if (_mosaicMode() === 'dwarf' && e.target.id === 'm-send') _dwSend(e.target); });
}

/* ---------- send to astro_dwarf_session (sequential, same payload as the Milky Way planner) ---------- */
async function _dwSend(btn) {
  var P = mosaicPlan, toSend = _dwSched.filter(function (t) { return t.ok; });
  if (!P.dwarfUid || !toSend.length) return;
  var exp = P.expSec, nat = _dwNative(P), count = _dwImgCount(P, exp, nat);
  btn.disabled = true; var okN = 0, errN = 0;
  for (var i = 0; i < toSend.length; i++) {
    var t = toSend[i]; btn.textContent = 'Sending ' + (i + 1) + '/' + toSend.length + '…';
    var payload = {
      dwarfUid: P.dwarfUid, target: { name: t.name, ra: t.raH, dec: t.dec }, camera: P.camera,
      exposure: String(exp), gain: String(P.gain), count: count,
      date: t.start.getFullYear() + '-' + _dwPad(t.start.getMonth() + 1) + '-' + _dwPad(t.start.getDate()),
      time: _dwPad(t.start.getHours()) + ':' + _dwPad(t.start.getMinutes()) + ':' + _dwPad(t.start.getSeconds()),
      autofocus: P.autofocusFirstOnly ? (t.row === 0 && t.col === 0) : true
    };
    if (nat.on) {   // native Dwarf mosaic: the Dwarf shoots the panels itself
      var mos = { doMosaic: nat.n > 1,                    // both axes at 100 -> no mosaic -> doMosaic false
                  framingX: nat.fx, framingY: nat.fy,
                  mosaic_count: count };                   // images PER panel
      payload.count = count * nat.n;                      // total images = mosaic_count x panels (e.g. 20 x 2 = 40)
      if (DW_MOSAIC_IN_SETUP_CAMERA) payload.setup_camera = mos; else Object.assign(payload, mos);
    }
    // Absolute instants: the server converts them to the Dwarf's site time
    // (this browser may be in another timezone, e.g. remote access).
    payload.startEpochMs = t.start.getTime();
    if (P.durationMode === 'duration' && nat.n === 1) {
      payload.endTime = _dwPad(t.end.getHours()) + ':' + _dwPad(t.end.getMinutes());
      payload.endEpochMs = t.end.getTime();
    }
    try {
      var res = await fetch(_dwApiBase() + '/api/program', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      var data = await res.json(); if (!res.ok || data.error) errN++; else okN++;
    } catch (err) { errN++; }
  }
  _dwStatus = okN + (nat.on ? ' mosaic(s) sent' : ' tile(s) sent') + (errN ? ', ' + errN + ' failed' : '') + '. Arm the device on the Programs page so the schedule starts automatically.';
  renderMosaic();
}
