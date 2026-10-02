// js/dwarf-scheduler.js

// -- DWARF NATIVE SCHEDULER (DEF-XXX) --------------------------------------------
// "Program this session to the Dwarf" - packages the current Best-of-Tonight
// plan cards into the shape described by DwarfLab's "Embedded scheduled
// shooting" spec (module 13, CMD_SYNC_SHOOTING_SCHEDULE = 16100, protocol
// >=1.9). We build the JSON/JS-object shape 1:1 from that doc's field names
// (ShootingScheduleMsg / ShootingTaskMsg -5.3) so a small local bridge script
// (dwarf_schedule_bridge.py, see chat) can serialize it to protobuf and push
// it to the Dwarf over its websocket. We do NOT talk protobuf/websocket
// directly from the browser - no compiled .proto classes are shipped to the
// page, and the Dwarf's control socket isn't reachable as plain JSON.
//
// ASSUMPTIONS (flagged - verify against the real device before relying on
// this for an unattended night):
//   - ra is exported in HOURS (0-24), matching this catalog's internal
//     convention (see _mosaicTarget's raH) - the spec doesn't state a unit.
//   - startTime/endTime are epoch MILLISECONDS (JS Date.getTime()).
//   - focusMode: 0 (autofocus) is used for every task; there's no per-target
//     autofocus toggle in the UI yet.
//   - filterModeIndex/filterModeName are taken from the existing
//     filterRec.filterId - the numeric *index* the device expects for a given
//     filter name is a firmware table we don't have locally, so filterMode is
//     left null and filterModeName carries the human name; the bridge script
//     is the place to map name ? index once you have that table.

var DWARF_SCHEDULE_BRIDGE_KEY = 'dso_dwarf_bridge_url';

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[c]);
}

function _dwarfDefaultBridgeUrl() {
  // If this page is being served BY astro_dwarf_session itself (see
  // components/api_routes.py's /catalog route - user-requested Sep 2026
  // specifically to fix mobile geolocation hanging on file:///content://,
  // which also solves this) - location.origin IS already the right
  // host:port, no IP to hand-type on a phone. Falls back to the old
  // localhost guess only for file:///content:// (location.origin is
  // "null" or the literal string "file://" there, never a real http(s)
  // origin an API call could use).
  if (/^https?:$/.test(location.protocol)) return location.origin + '/api/schedule';
  return 'http://127.0.0.1:8765/api/schedule';
}

function _dwarfBridgeUrl() {
  try { return localStorage.getItem(DWARF_SCHEDULE_BRIDGE_KEY) || _dwarfDefaultBridgeUrl(); }
  catch (e) { return _dwarfDefaultBridgeUrl(); }
}

function _dwarfSetBridgeUrl(url) {
  try { localStorage.setItem(DWARF_SCHEDULE_BRIDGE_KEY, url); } catch (e) {}
}

function _dwarfToast(msg) {
  // BUG FIX (Sep 2026): routed through the in-modal #dwarf-send-status
  // line first when the "Program session to the Dwarf" modal is open -
  // see that element's own comment for why the original bottom-of-
  // screen toast alone was invisible in that case (hidden behind the
  // modal's own much higher z-index). Still ALSO fires the original
  // toast underneath - harmless, and covers the (rarer) case where
  // this is called with the modal already closed.
  var inModal = document.getElementById('dwarf-send-status');
  if (inModal) {
    var isError = /fail|error|refused|unreachable|stale/i.test(msg);
    inModal.textContent = msg;
    inModal.style.color = isError ? 'var(--red,#e05a5a)' : 'var(--teal,#4fd8c8)';
  }
  var t = document.getElementById('mosaic-toast');
  if (t) { 
    t.textContent = msg; 
    t.classList.add('show'); 
    setTimeout(function () { t.classList.remove('show'); }, 2200); 
  } else { 
    console.log('[Dwarf] ' + msg); 
  }
}

function _dwarfUuid() {
  // "UUID" + millisecond timestamp, per §3.2.3 iOS/Android rule - reused
  // verbatim here so schedules created by this page sort/compare the same
  // way as ones created by the official app.
  var uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
  return uuid + Date.now();
}

const _DWARF_FILTER_DEVICE_NAME = {
  // Maps FILTER_CATALOG ids (this catalog's own vocabulary) to the
  // Dwarf's own filter names (AllowedIRFilter/AllowedIRFilterMini in
  // dwarf_python_api's data_utils.py - index 1/2 share these exact
  // names on both D3 and Mini; only index 0's name differs by model,
  // and neither dwarf-astro nor dwarf-duo maps to index 0).
  'dwarf-astro': 'Astro Filter',
  'dwarf-duo': 'Duo-Band Filter',
  'dwarf-vis': 'VIS Filter',   // D3-only per FILTER_CATALOG's rigAvailability
};

function _dwarfTaskFromPlan(p) {
  const tuple = (p.id && typeof _findAtlasTupleById === 'function') ? _findAtlasTupleById(p.id) : null;
  const ra  = tuple ? tuple[2] : (p.ra != null ? p.ra : null);
  const dec = tuple ? tuple[3] : (p.dec != null ? p.dec : null);
  const fr = p.filterRec || {};

  return {
    name: p.name || 'Target Unknown',
    ra: ra,
    dec: dec,
    // startTime/endTime are NOT set here anymore - see _dwarfSequenceTasks
    // in buildDwarfShootingSchedule. p.usableStart/usableEnd is each
    // target's own VISIBILITY window (when it's above the horizon), not a
    // TIME SLOT - every plan card shares most of the same night, so using
    // usableStart/usableEnd directly gave every task nearly identical,
    // heavily overlapping start/end times. Field-confirmed (Sep 2026): a
    // schedule with several tasks sharing the same start/end was rejected
    // with CODE_SHOOTING_SCHEDULE_TIME_CONFLICT (-16302) - the Dwarf has
    // one camera, it can't image N targets in the same slot.
    _usableStart: (p.usableStart instanceof Date) ? p.usableStart.getTime() : (p.usableStart || Date.now()),
    _usableEnd:   (p.usableEnd   instanceof Date) ? p.usableEnd.getTime()   : (p.usableEnd || (Date.now() + 4 * 3600 * 1000)),
    startTime: null,
    endTime: null,
    // shutterIndex/gainIndex/filterModeIndex are resolved server-side
    // (dwarf_utils.py's perform_sync_shooting_schedule, via the real
    // AllowedExposures*/get_ir_filter_index_by_name lookup tables) - see
    // that function's own comment. Field-confirmed (Sep 2026): sending
    // these as null made the device accept the sync (code 0) but then
    // fail every task instantly (SHOOTING_TASK_STATUS_FAILED, code -1)
    // without ever attempting to point - it needs the real numeric
    // index, a human-readable name alone isn't enough.
    shutterIndex: null,
    shutterName: fr.subSec != null ? String(fr.subSec) : (p.exp ? String(p.exp) : null),
    gainIndex: null,
    gainName: fr.gain != null ? String(fr.gain) : (p.gain ? String(p.gain) : null),
    // count: 0, NOT null - field-confirmed (Sep 2026): the official
    // app's own successful schedules (a real device dump via CMD_GET_
    // ALL_SHOOTING_SCHEDULE) always send count:0, never null/omitted -
    // 0 apparently means "shoot until the task's own end_time", the
    // catalog page's actual intent here (it never computes a target
    // shot count). Sending null instead triggered CODE_SHOOTING_
    // SCHEDULE_INVALID_SHOOTING_DURATION (-16301) on a real device,
    // even with an otherwise perfectly reasonable window/exposure.
    count: 0,
    stacked: 0,
    filterModeIndex: null,
    // Was fr.filterId directly (this catalog's own id, e.g. "dwarf-
    // astro") - the Dwarf's own lookup table has never heard of that
    // string. Mapped to the device's real filter name so dwarf_utils.py
    // can resolve an index from it.
    filterModeName: _DWARF_FILTER_DEVICE_NAME[fr.filterId || p.filterId] || fr.filterId || p.filterId || null,
    schedule_task_id: _dwarfUuid(),
    createFrom: 2,
  };
}

function _dwarfSequenceTasks(tasks) {
  // Give each task a NON-OVERLAPPING consecutive slot instead of its raw
  // visibility window (see _dwarfTaskFromPlan's comment - overlapping
  // slots are what triggered CODE_SHOOTING_SCHEDULE_TIME_CONFLICT).
  //
  // v1, intentionally naive: sort by usableEnd ascending (the target that
  // sets/becomes unusable soonest goes first - standard astro-imaging
  // practice, don't lose a setting object waiting on one with more
  // margin), then split the combined [earliest usableStart, latest
  // usableEnd] window into N EQUAL slots in that order. This does NOT
  // try to keep every task within its own usableStart/usableEnd (a
  // target near the end of the queue may get a slot that starts after
  // its own ideal window began, or extends past its own peak) - proper
  // altitude-aware time-boxing (e.g. weighting by each target's own
  // usableHours, or clipping to its own window and redistributing
  // leftover time) is a real future improvement, not attempted here.
  // This is the minimum fix to stop the device from rejecting the
  // schedule outright.
  const withWindow = tasks.filter(t => t._usableStart != null && t._usableEnd != null);
  if (!withWindow.length) return [];
  const sorted = withWindow.slice().sort((a, b) => a._usableEnd - b._usableEnd);
  const totalStart = Math.min.apply(null, sorted.map(t => t._usableStart));
  const totalEnd   = Math.max.apply(null, sorted.map(t => t._usableEnd));
  const perSlot = (totalEnd - totalStart) / sorted.length;

  return sorted.map((t, i) => {
    const startTime = Math.round(totalStart + i * perSlot);
    const endTime   = Math.round(totalStart + (i + 1) * perSlot);
    const { _usableStart, _usableEnd, ...clean } = t;
    return { ...clean, startTime, endTime };
  });
}

export function buildDwarfShootingSchedule(plans, meta = {}) {
  const site = (typeof getActiveLocation === 'function') ? getActiveLocation() : null;
  const rawTasks = (plans || []).map(_dwarfTaskFromPlan).filter(t => t.ra != null && t.dec != null);
  const tasks = _dwarfSequenceTasks(rawTasks);
  const starts = tasks.map(t => t.startTime).filter(x => x != null);
  const ends   = tasks.map(t => t.endTime).filter(x => x != null);
  
  const title = meta.title || meta.siteName || 'Session';

  return {
    scheduleId: _dwarfUuid(),
    scheduleName: title + ' - ' + ((site && site.name) || 'site') + ' - ' + new Date().toLocaleDateString('en-CA'),
    startTime: starts.length ? Math.min.apply(null, starts) : null,
    endTime:   ends.length   ? Math.max.apply(null, ends)   : null,
    lock: 0,
    password: '',
    paramsMode: 0,
    params: {
      longitude: site ? site.lon : null,
      latitude:  site ? site.lat : null,
      cityName: (site && site.name) || '',
      focusMode: 0,
    },
    shooting_tasks: tasks,
  };
}

function _dwarfStalenessWarning(sched) {
  // Field-confirmed (Sep 2026): the Dwarf rejects a schedule whose
  // start_time is too far from "now" with CODE_SHOOTING_SCHEDULE_
  // START_TIME_TOO_FAR (-16308, PDF §6.1, "exceeds 12 hours"). The most
  // common way to hit this isn't a real scheduling mistake - it's simply
  // that the catalog page computes "tonight"'s sunset/sunrise window
  // ONCE at page load, using the date at that moment; leaving the tab
  // open across a day boundary (or just walking away for a while) means
  // every plan card keeps showing yesterday's night, silently, with no
  // visual cue that anything is stale. Checked client-side here so the
  // person gets a clear "reload the page" message instead of a bare
  // error code after a failed device round-trip.
  const now = Date.now();
  const TWELVE_H = 12 * 60 * 60 * 1000;
  if (sched.endTime && sched.endTime < now) {
    return "⚠ This plan's whole window has already ended — the page was likely left open since an earlier day. Reload the page (not just \"roll again\": that only reshuffles targets, it doesn't recompute tonight's date) before sending.";
  }
  // Starting MORE than 12h from now is fine: the bridge keeps it pending
  // and syncs it automatically once within 12h (device-confirmed limit,
  // Oct 2026). Only a start long PAST means yesterday's stale plan.
  if (sched.startTime && now - sched.startTime > TWELVE_H) {
    return "⚠ This plan's start time is more than 12h in the past — reload the page to recompute tonight's window before sending.";
  }
  return null;
}

function _dwarfSummaryHtml(sched, selectedIds) {
  const hhmm = ms => ms ? new Date(ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '—';
  const rows = sched.shooting_tasks.map(t =>
    '<tr><td><input type="checkbox" class="dwarf-task-checkbox" data-plan-id="' + escapeHtml(t.planId) + '"' +
      (selectedIds.has(t.planId) ? ' checked' : '') + '></td>' +
    '<td>' + escapeHtml(t.name) + '</td><td>' + hhmm(t.startTime) + '–' + hhmm(t.endTime) +
    '</td><td>' + escapeHtml(t.shutterName || '—') + 's @ ' + escapeHtml(t.gainName || '—') +
    '</td><td>' + escapeHtml(t.filterModeName || '—') + '</td></tr>'
  ).join('');
  return '<table class="dwarf-sched-table"><thead><tr><th></th><th>Target</th><th>Window</th><th>Exp/Gain</th><th>Filter</th></tr></thead>' +
         '<tbody>' + rows + '</tbody></table>';
}

export function openDwarfProgramPanel(plans, meta) {
// Accepte plans s'il s'agit d'un tableau unique ou d'un seul objet cible
  const planList = Array.isArray(plans) ? plans : [plans];
  const valid = planList.filter(p => p && (p.id || p.name));
  
  if (!valid.length) { 
    _dwarfToast('No plans to program.'); 
    return; 
  }

  // Default title configurable according to the source (e.g., "Favorites", "Search Results", "Mosaic")
  const sessionTitle = meta.title || meta.siteName || 'Custom selection';

  // Every plan starts checked; unchecking one re-flows the remaining
  // targets' time slots (see _dwarfSequenceTasks) rather than leaving a
  // gap where the deselected target used to sit.
  const selectedIds = new Set(valid.map(p => p.id));
  let sched = null;   // (re)built by rebuild(), read by the button handlers via closure
  let json = '';

  let ov = document.getElementById('dwarf-sched-overlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'dwarf-sched-overlay';
    ov.style.cssText = 'position:fixed;inset:0;background:rgba(4,8,16,.82);z-index:9500;display:flex;align-items:center;justify-content:center;padding:16px';
    document.body.appendChild(ov);
  }
  ov.innerHTML =
    '<div style="background:var(--panel,#0a1020);border:1px solid var(--border2,#243550);border-radius:10px;max-width:640px;width:100%;max-height:86vh;overflow:auto;padding:18px;font-family:var(--body,sans-serif);color:var(--text,#c8d8f0)">' +
      '<div style="font-family:var(--head,sans-serif);font-size:20px;margin-bottom:4px">Program session to the Dwarf</div>' +
      '<div id="dwarf-dynamic-region"></div>' +
      '<div style="margin-top:14px;font-size:11px;color:var(--text3,#4a6a95)">astro_dwarf_session URL (run it with a fixed --port):</div>' +
      '<input id="dwarf-bridge-url" type="text" value="' + escapeHtml(_dwarfBridgeUrl()) +
        '" style="width:100%;box-sizing:border-box;margin:4px 0 8px;padding:6px 8px;background:var(--bg3,#0d1526);border:1px solid var(--border,#1c2c48);border-radius:6px;color:inherit;font-family:var(--mono,monospace);font-size:12px">' +
      '<div style="font-size:11px;color:var(--text3,#4a6a95)">Target Dwarf:</div>' +
      '<select id="dwarf-target-select" style="width:100%;box-sizing:border-box;margin:4px 0 12px;padding:6px 8px;background:var(--bg3,#0d1526);border:1px solid var(--border,#1c2c48);border-radius:6px;color:inherit;font-size:12px">' +
        '<option value="">Loading devices…</option>' +
      '</select>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
        '<button type="button" id="dwarf-btn-send" class="btn-plan-mosaic">⇪ Send to bridge</button>' +
        '<button type="button" id="dwarf-btn-copy" class="btn-plan-mosaic">⧉ Copy JSON</button>' +
        '<button type="button" id="dwarf-btn-dl" class="btn-plan-mosaic">⬇ Download .json</button>' +
        '<button type="button" id="dwarf-btn-close" class="btn-plan-mosaic" style="margin-left:auto">Close</button>' +
      '</div>' +
      // BUG FIX (Sep 2026, user-reported: "pas de retour visuel en cas de
      // success ou d'erreur"): _dwarfToast()'s bottom-of-screen toast has
      // z-index:2400, but THIS modal (#dwarf-sched-overlay) has z-index:
      // 9500 and stays open while sending - every toast triggered from a
      // button in here (Send, Copy, Download) was rendering completely
      // hidden behind the modal itself, invisible until the person closed
      // it. This status line sits INSIDE the modal instead, impossible to
      // hide behind it - see _dwarfToast's own updated comment for how
      // messages get routed here now.
      '<div id="dwarf-send-status" style="margin-top:10px;font-size:12px;min-height:1.4em"></div>' +
    '</div>';

  const dynamicRegion = document.getElementById('dwarf-dynamic-region');
  let stalenessWarning = null;

  function rebuild() {
    const chosen = valid.filter(p => selectedIds.has(p.id));
    sched = buildDwarfShootingSchedule(chosen, meta);
    // planId threaded through here (not inside buildDwarfShootingSchedule
    // itself) so the checkbox row can be matched back to a plan without
    // changing the wire schema the device actually receives.
    sched.shooting_tasks.forEach((t, i) => { t.planId = chosen[i] && chosen[i].id; });
    json = JSON.stringify(sched, null, 2);
    stalenessWarning = sched.shooting_tasks.length ? _dwarfStalenessWarning(sched) : null;

    const n = sched.shooting_tasks.length;
    dynamicRegion.innerHTML =
      '<div style="font-size:12px;color:var(--text2,#7a9bc5);margin-bottom:12px">' +
        (n || 'No') + ' target(s) selected, ' + escapeHtml(sched.scheduleName) + '. This builds a native ' +
        'shooting-schedule payload (CMD_SYNC_SHOOTING_SCHEDULE) — see the caveats in the console/source ' +
        'before trusting it unattended. Untick any target below to leave it out — the rest re-flow to fill its slot.</div>' +
      (stalenessWarning ? '<div style="background:rgba(180,60,30,.18);border:1px solid rgba(220,100,60,.5);border-radius:6px;padding:8px 10px;margin-bottom:12px;font-size:12px;color:#ffb08a">' + escapeHtml(stalenessWarning) + '</div>' : '') +
      (n ? _dwarfSummaryHtml(sched, selectedIds)
         : '<div style="font-size:12px;color:var(--text3,#4a6a95);padding:8px 0">Nothing selected — tick at least one target above.</div>');
  }

  // Event delegation on the dynamic region: rows are replaced wholesale on
  // every rebuild(), so a single listener here survives that instead of
  // needing to be re-attached per checkbox each time.
  dynamicRegion.addEventListener('change', e => {
    if (!e.target.matches('.dwarf-task-checkbox')) return;
    const id = e.target.getAttribute('data-plan-id');
    if (e.target.checked) selectedIds.add(id); else selectedIds.delete(id);
    rebuild();
  });

  rebuild();
  document.getElementById('dwarf-btn-close').addEventListener('click', () => ov.remove());
  ov.addEventListener('click', e => { if (e.target === ov) ov.remove(); });
  document.getElementById('dwarf-btn-copy').addEventListener('click', () => {
    if (!sched.shooting_tasks.length) { _dwarfToast('Nothing selected — tick at least one target.'); return; }
    navigator.clipboard.writeText(json).then(() => _dwarfToast('Schedule JSON copied.'),
      () => _dwarfToast('Copy failed — select the text manually.'));
  });
  document.getElementById('dwarf-btn-dl').addEventListener('click', () => {
    if (!sched.shooting_tasks.length) { _dwarfToast('Nothing selected — tick at least one target.'); return; }
    const blob = new Blob([json], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'dwarf-schedule-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  });

  // Fetch the device list directly from astro_dwarf_session's own REST API
  // (GET {base}/api/dwarfs — see components/api_routes.py). Run
  // astro_dwarf_session with a fixed --port so this URL stays stable
  // across restarts; the default NiceGUI port is otherwise randomized.
  const select = document.getElementById('dwarf-target-select');
  const bridgeUrlForDevices = () => document.getElementById('dwarf-bridge-url').value.trim().replace(/\/api\/schedule\/?$/, '');
  const loadDevices = () => {
    fetch(bridgeUrlForDevices() + '/api/dwarfs')
      .then(res => res.json())
      .then(data => {
        const devices = (data && data.devices) || [];
        if (!devices.length) {
          select.innerHTML = '<option value="">No known Dwarf (check devices.json on the bridge)</option>';
          return;
        }
        select.innerHTML = devices.map(d =>
          '<option value="' + escapeHtml(d.dwarfUid) + '">' + escapeHtml(d.name) +
          (d.connected ? (d.busy ? ' — connected (busy)' : ' — connected') : ' — offline') +
          (d.hasPending ? ' (pending schedule queued)' : '') + '</option>'
        ).join('');
      })
      .catch(() => {
        select.innerHTML = '<option value="">Bridge unreachable — devices unknown</option>';
      });
  };
  loadDevices();
  document.getElementById('dwarf-bridge-url').addEventListener('change', loadDevices);

  document.getElementById('dwarf-btn-send').addEventListener('click', () => {
    // BUG FIX (Sep 2026, field-confirmed): this used to send whatever
    // `sched` last happened to be (built by rebuild(), only re-run on a
    // checkbox toggle) - clicking Send twice without touching a
    // checkbox in between resent the exact SAME scheduleId/task ids
    // both times. A real device test showed the SECOND identical send
    // (right after the schedule had already been synced once, then
    // deleted via astro_dwarf_session's own UI) came back WS_PARSE_
    // PROTOBUF_ERROR (-1) - a random UUID landing on the exact same
    // value twice by chance is essentially impossible, so this was the
    // cause, not a coincidence. rebuild() here guarantees a fresh id
    // on every actual send, independent of whether a checkbox changed.
    rebuild();
    if (!sched.shooting_tasks.length) { _dwarfToast('Nothing selected — tick at least one target.'); return; }
    if (stalenessWarning) {
      _dwarfToast('Refused to send a stale schedule — reload the page first (see the warning above).');
      return;
    }
    const url = document.getElementById('dwarf-bridge-url').value.trim();
    _dwarfSetBridgeUrl(url);
    const dwarfUid = select.value;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dwarfUid: dwarfUid, schedule: sched }),
    })
      .then(res => {
        // BUG FIX (Sep 2026, user-reported: "bizarre le Dwarf est bien
        // connecté"): status 502 specifically is api_routes.py's OWN
        // deliberate choice for "the bridge WAS reached fine, but the
        // device itself rejected perform_sync_shooting_schedule" - not
        // a real connectivity failure. A genuine network failure never
        // reaches this .then() at all (it throws before res exists,
        // landing straight in .catch() with a different err.message
        // like "Failed to fetch"), so 502 here is unambiguous - read
        // its JSON body (now includes the real DwarfErrorCode name,
        // e.g. "CODE_SHOOTING_SCHEDULE_TIME_CONFLICT", per user request
        // Sep 2026: "ce message m'intéresse plus que... check the log")
        // rather than just tagging it generically.
        if (res.status === 502) {
          return res.json().catch(() => ({})).then(body => { throw new Error('DEVICE_SYNC_FAILED:' + (body.reason || '')); });
        }
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json().catch(() => ({}));
      })
      .then(data => {
        const label = dwarfUid && select.selectedOptions[0] ? select.selectedOptions[0].textContent : url;
        if (data && data.mode === 'deferred') {
          const at = data.syncAt ? new Date(data.syncAt).toLocaleString() : '?';
          _dwarfToast('Saved for ' + label + ' — the Dwarf only accepts a schedule within 12h of its start, so it will be synced automatically from ' + at + ' (app running, Dwarf connected).');
        } else if (data && data.mode === 'pending') {
          _dwarfToast(label + ' is offline — schedule queued, will be offered on next connect.');
        } else if (data && data.mode === 'busy_pending') {
          _dwarfToast(label + ' is busy (manual/scheduled session running) — schedule queued, offered once it frees up.');
        } else {
          _dwarfToast('Sent “' + sched.scheduleName + '” (' + sched.shooting_tasks.length + ' target(s)) to ' + label + '.');
        }
      })
      .catch(err => {
        if (err.message.startsWith('DEVICE_SYNC_FAILED')) {
          const reason = err.message.split(':')[1];
          _dwarfToast(reason
            ? 'Device rejected the schedule: ' + reason
            : 'Sent to the bridge, but the device rejected the schedule — check the astro_dwarf_session log for the error code.');
        } else {
          _dwarfToast('Bridge unreachable (' + err.message + ') — is astro_dwarf_session running?');
        }
      });
  });
}
