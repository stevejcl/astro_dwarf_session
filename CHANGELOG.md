# Changelog

## [3.2.6] - 2026-10-17
  ### Add
    ### Eclipsing binaries: your own elements for a star
    (user-asked Oct 2026: RZ Dra's VSX elements, of 1979, put its minimum at 21:01 - it came at about 22:58, the
    Krakow up-to-date elements right) In the planner's star list, a pencil per star: a primary minimum (HJD) and the
    period, kept over VSX's (refresh included), used for its minima; "Back to VSX's" drops them. They are shared with
    Scope Archive's Siril photometry script (star_elements.json in the user folder) for the O-C.
    ### Repair session for a failed capture
    (user-asked Oct 2026, from DwarfLab's procedure) A capture that failed (Dwarf hung, battery, reboot) keeps its
    images on the Dwarf but has no stacked image: not in the Album nor the Megastack. In Results, an Error program
    offers "Repair session": the same program again with 2 images (same target, exposure, gain and filter), a
    session entry in the Album that Dwarfium Scope Archive's Repair fills with the failed capture's images
    (repair_of in its file: the failed capture's start). Asked first - the Dwarf moves to the target.
    Once that session is done, its result offers "Finish the repair in Scope Archive": Scope Archive's Repair opens
    (in its window when it has one) with this session and the failed capture already found on the Dwarf - check,
    Start Repair, reboot the Dwarf, then a Megastack in the Dwarf app. Shown when Scope Archive's URL and Dwarf Id are
    set in the Dwarf's Settings.
    ### My objects, favourites and recent targets in "Pick from catalog"
    (user-requested Oct 2026, issue #162) A target from Stellarium, typed in, a variable star or a recent one is
    kept in "my objects" (catalog_add_on.json, read by Scope Archive too) when "Keep in my objects" is ticked on
    saving the program - its name, RA and Dec are enough, the choice remembered; not offered for a catalog object.
    In "Pick from catalog": a star marks a favourite (favorites.json in the user's folder - using a target doesn't
    make it one); the recent targets are those of the programs run (Done / Error of every Dwarf), with their last
    use, a recent one not in the catalog picked with its program's description or kept in my objects with a pin;
    favourites, recent targets and my objects listed first, a filter shows one of them only; "Add an object", and
    my objects edited or removed there. catalog_add_on.json, when Scope Archive isn't installed next to the app, now
    lives in ~/.astro_dwarf_session (moved once from assets/, which an update may replace); a user object later
    found in the shared catalog is shown once, its favourite kept.
    ### Pick from catalog: a search that finds what you mean, and a phone layout
    (user-requested Oct 2026, issue #162) Case, accents, spaces, punctuation and leading zeros ignored, "Messier"
    read as "M" - "m42", "M 42", "Messier 42", "NGC 01976" find M 42 -, across the designation, the display name
    and the alternate names; best match first (exact, starts with, contains, then every word found), Enter picks
    the first result, "nothing found" says how to add it. On a phone the name and type under the designation, the
    other columns hidden, the filters side by side. The help and the files' paths behind an info button.
    ### Full-screen live stacking view
    The card's and the device page's full-screen button opened the Dwarf's raw image alone in a browser tab
    (user-requested Oct 2026, issue #164). It now opens a view in the app (/live/<uid>): the last stacked image,
    replaced once the next one is loaded, with the target, the progress (stacked / taken / total, end time) and the
    camera's settings over it - hidden with a button, remembered by the browser. Display adjustments (brightness,
    contrast, saturation, black point, gamma) kept by the app for each Dwarf, never sent to it nor written in a file;
    zoom and pan (wheel, pinch, double click or tap to reset) each viewer's own. On a DWARF mini, the only one
    stacking with both cameras, the other one in a small inset: swapped with a click, hidden with a button. A
    megastack shows its stack and its progress. Watch: the device page shows the stacked image (no longer the
    streams) as adjusted from the control app, a click opens the same view (/watch/<uid>/live) without the
    adjustments; the dashboard cards' images are adjusted too. The image goes through this app
    (/live/frame/<uid>/<cam>): one request to the Dwarf per new image whatever the number of viewers, seen from a
    phone over HTTPS or Tailscale too.
    ### A Dwarf's name: shown, and renamed in its Settings
    The name typed when a Dwarf was added (Bluetooth pairing, manual configuration) was kept in devices.json but
    shown nowhere - every page showed its uid (user-reported Oct 2026). It is now the title of its dashboard card, its
    page, its Programs and Settings and its Watch page, the uid under it; a "Dwarf name" field in its Settings renames
    it - its display name only, the uid and the config files stay (programs, Scope Archive link and Hub untouched).
    ### HTTPS for phones: the app full screen on Android
    Optional, in a device's Settings ("HTTPS for phones"; user-requested Oct 2026, from a fork's commit by
    nhat-bui-dk): Android installs the app full screen only over HTTPS. Once on, this PC also answers in HTTPS on port
    8443 - a relay to the normal HTTP server, which with the PC's window stays unchanged. Its certificate (localhost,
    <name>.local, the PC's LAN and Tailscale addresses) is signed by Dwarfium's certificate authority when its folder
    is given (CADwarfiumCert.pem + CADwarfiumKey.pem - user-asked: a phone that trusts Dwarfium needs nothing more),
    else by this app's own, limited to private networks, Tailscale and .local; signed again at startup when an address
    or the authority changes. QR codes to install the authority on the phone (/https/ca.crt) and open the app.
    Opening Scope Archive from a phone works through the relay too. New requirement: cryptography.
    ### Archive from a phone over HTTPS: always on the phone
    Through the HTTPS relay, the Explorer's and the session page's Archive buttons opened Scope Archive on the PC,
    sometimes on the phone (user-reported Oct 2026): the page's own request, by which the phone was recognized, is
    often closed by the time of the click. The page's websocket, open as long as the page, tells it then.
    ### Phone layout: Settings and program editor
    The "HTTPS for phones" card last in the Settings, after "Manually update IP" (user-asked Oct 2026). Program
    editor, manual target: the icon of "Get from Stellarium", "Pick from catalog" and the variable star button kept
    left of its text, which wraps beside it, on a phone (the text went under the icon).
    ### Pulsating stars: their maxima
    A pulsating star (VSX type SXPHE, DSCT, HADS, RR, CEP, CW...; user-requested Oct 2026: DY Peg listed as an eclipsing
    binary's minimum) is shown with its maxima - "max" in the list, "Pulsating star ... maximum predicted" in the
    program's description -, no secondary, a window of 0.6 period on each side (a whole cycle, 30 min to 1.5 h). The
    dialog and its button named for both ("Variable star: min / max").
    ### Eclipsing binary minima: from tonight
    The minima list starts from tonight (site time), no longer from the program's own date, which may already be the
    next day (user-reported Oct 2026: DY Peg's minimum picked at 19:30 dated the next day); a "Night of" field picks
    another night.
    ### Archive in Dwarfium Scope Archive from a phone
    Clicked on a phone (or another device of the LAN - user-requested Oct 2026: the capture launched from the phone,
    its archive opened on the PC), the Scope Archive page opens on that device when Scope Archive answers on the LAN
    (started with --lan): its address the PC's as the phone reaches this app (LAN, Tailscale) when the Settings URL is
    one of this PC's - localhost, its LAN IP while the phone comes through Tailscale (both apps on the PC) -, another
    machine's kept, a link to tap (a tab opened after the round trip is blocked by the phone's browser). Else it opens
    in Scope Archive's window on the PC as before, "Opened on the PC" shown on the phone. Programs page and Explorer.
    ### Program editor: eclipsing binary minima (variable stars)
    Dwarfs with nothing to do can time variable stars (user-requested Oct 2026: plan and capture here, measure in Siril
    or AstroImageJ). Optional: a button at the top right of the Programs page turns it on for this run of the app (off
    at each start) and loads the stars' elements. Then an "Eclipsing binary minimum" button next to "Pick from
    catalog": the next minima (primary, optionally secondary) of eclipsing binaries over the coming nights, seen from
    the Dwarf's site - time, altitude,
    the window around the minimum (half the eclipse + 30 min each side when its duration is known, else +/- 1.5 h)
    and whether all of it is dark and high enough. A click sets the target, RA/Dec, a description with the predicted
    minimum and its HJD, the start / end time and the image count, and the IR filter cutting the infrared (VIS on a
    DWARF 3, IR cut on a DWARF II - the sensor's green pixels let some infrared through).
    Stars and elements in eclipsing_binaries.json (working folder). About thirty bright Algol-type stars come with the
    app, their elements from the AAVSO's VSX (assets/eclipsing_binaries_seed.json - fetching them on first use took a
    while). Others are added by name (fetched from VSX, api.object), or with an epoch / period of one's own (kept over
    VSX's). "Update from VSX" refreshes them: 4 stars at a time, one update shared by the Programs page's button and
    the dialog, its progress on the button, a network error retried once. The star list says why a star has no
    elements: not found, VSX not reached, or no epoch / period in VSX (to type in).
    Minima corrected for the light time to the Sun (HJD), within a few seconds of astropy.
    ### Catalog, Mosaic Inspector: the plate-solve from a .wcs file
    The DWARF's FITS have no plate-solve (WCS) in their header, and the Inspector skipped them (user-requested Oct
    2026). A frame takes it from its .wcs file selected with it - same name (MW_Tile_R1C1.fits +
    MW_Tile_R1C1.wcs), as Dwarfium Scope Archive's Milky Way tab, ASTAP or astrometry.net write it: a header-only
    FITS or plain text cards (ASTAP), the CD matrix or PC + CDELT. A frame without either says to select its .wcs.
    Its footprints and composite are now drawn in a stereographic frame, each panel's edge sampled through its
    plate-solve (lens distortion): the gnomonic frame drew straight-edged panels that a wide field (a 120 deg Milky
    Way mosaic) stretched into long wedges at its edges - the panels now keep their real shape.
    ### Milky Way planner: foreground pass
    The foreground (trees, roof) is attached to the ground, the sky turns 15 deg an hour: over a 2 h mosaic each tile
    shows it elsewhere against the stars. New "Foreground pass" (at the start or at the end of the series, 5 images per
    tile by default, at most 5 - the Dwarf dithers after the 6th): the same tiles again, one after the other, named
    "MW Tile R1C1 Decor", so the foreground freezes at almost the same time on every tile and the sky behind it is the
    tiles' own - for the Milky Way tab of Dwarfium Scope Archive to put it back in front of the mosaic. Foreground
    entries only need to be above the horizon, don't focus (the first entry of the sequence does) and never use the
    fixed-duration end time.
    ### After the session and end of the night
    After a capture the Dwarf stayed on its end-of-session screen, still tracking (battery), and powered off while
    tracking the D3 / Mini don't close their lenses (from rest they do - user-tested). New card in the Programs page's
    Scripts tab, per Dwarf (end_of_night.json):
    - Leave the end-of-session screen N min (5 by default) after each capture - a program, a capture from the
      Actions, the Dwarf's own schedule while connected: Go Live, and Stop goto (the tracking) if ticked. A program
      can override it in the editor ("After the session"); nothing after a program stopped by the user.
    - End of the night, X min after the last capture (off by default): close the lenses when the next planned
      activity is more than 15 min away, or power the Dwarf off - only when nothing is planned any more (programs
      in ToDo, tasks of the Dwarf's schedule, a schedule waiting to be sent): a remote Dwarf can't be switched back
      on. Go Live, Stop goto and the lenses closed (Pitch: motor_action 12 on D2, 1 on D3 / Mini - dwarf_python_api
      3.1.6) always come before the power off. The card shows the estimated time.
      Never while a schedule of the Dwarf itself is planned or waiting to be sent: it must stay on and as set up -
      it sleeps when idle and wakes before its tasks (DwarfLab: "Do not power off after sync").
    - Initial position: the Pitch position (and the Rotation on D2 / D3: the night's last goto turned it - not on
      the Mini, its Rotation can't be reset) saved after each successful calibration of a program, or by the user
      (Actions: "Save position"). New program step "Start position" (saved initial position - axes
      reset then back to it, the polar position when none is saved - or the polar position); done anyway when this
      app closed the lenses, so a remote Dwarf never stays closed.
    - Actions: "Close the lenses", "Initial position" (go to it), "Save position".
      The Dwarf gives a motor position only once its axis was reset since it was switched on (NEED RESET): saving
      by hand resets the axes first (a reset goes to the limit and comes back to where the axis was).
    - "Bulky accessory mounted" (a cap, a thick filter holder on a D3): folding the Pitch could make it touch -
      closing, a Pitch reset (to its limit), the Dwarf powering off from rest. Then no end-of-night closing or power
      off, no start position in programs, and a confirmation for the Polar position, Close the lenses, Go to / Save
      the initial position. A filter on the D2's own magnetic holder doesn't touch.
      To use with an accessory: calibrate (or save the initial position) first, then mount it and tick the box. Lenses
      closed by this app a night before and the box ticked: not reopened by programs - said in the steps and on the
      card ("It is open" once opened by hand).
    A delay in progress is kept in memory only (lost if the app restarts).
    ### Camera settings: number of frames
    A capture started from the Actions used the count left in the Dwarf by its last session. "Frames" is now on the
    wide row of the device page's camera settings (third, under the tele filter): sent on Enter or when leaving
    the field, for both cameras.

    ### Megastack (asked by Scope Archive)
    The Dwarf stacks several of its sessions of a target together - or restacks a single one - (FITS still on its
    disk) into Astronomy/RESTACKED/, like the official app's megastack (its commands found by a capture,
    dwarf_python_api 3.1.6). Asked through POST /api/megastack (Scope Archive's Explore), run as a program: the
    Dwarf checks the sessions (refused with its reason: target, binning, missing dark frames - mixed filters it
    takes, e.g. Duo-Band with Astro), starts, then is followed until its stack is in the album - its steps, then its
    progress, shown alike on every screen - the home screen card, the device page (its banner at the top and its program), the watch page (its
    banner and Tele card) - like a capture's: "Megastack in progress · 436/598 · 399 stacked" (images processed / to
    stack, stacked so far - read from the result's shotsInfo.json, the rejected ones count as processed); the result
    in the Results tab (View shows it). Nothing else runs on the Dwarf meanwhile.
    Its total exposure (the listing and shotsInfo.json have none) is read at its end from its stacked FITS, as Scope
    Archive does - EXPTIME of its header, only the header fetched; a mosaic's is the sum of its panels' - shown in
    its last step, its Results tab card and the Explorer's view of a megastack result (under a second - the Sun's
    - in ms, was "0s"). At its end, its counts and total exposure only: not the camera's settings of the moment
    (the Sun's 1/10000 was shown as its exposure).
    Sessions whose FITS are no longer on the Dwarf (its folders listed over FTP) are named and refused before
    anything is sent - the Dwarf's own check let them through, then refused the start (INVALID_DATA, user-seen).
    On the home screen, the Dwarf's card - and on the device and watch pages, the Tele frame - show the stack as it
    grows instead of the Tele preview (nothing to see there meanwhile), back to the Tele preview after it - for a
    megastack run by this app or by the official app. The image is fetched by this app (its name read over FTP: stacked_thumbnail_
    <target>_<filter>_<stamp>.jpg while it stacks) and only a complete one kept: read directly, the browser got
    half-written images while the Dwarf rewrote it (user-seen). Fetched again only once more images were
    processed (shotsInfo.json), a half-written one tried again at the next check.
    Also from this app: the Explorer page's Megastack button (top right) - tick sessions of a target (single
    captures, or mosaics - not mixed; another target or a megastack result is refused), then Megastack: the same
    program, followed on the device page. A mosaic's FITS are in its panels' subfolders: looked for there too
    (not in a thumbnail folder).
    Its selection mode shows only the sessions that can be megastacked (not a megastack result), grouped by
    target (A-Z, a header with its count, newest first in each); back to the whole gallery after it.
    ### Explorer gallery: the target on each tile
    Above its date (was the date only).
    ### Wake up a Dwarf from the phone (hotspot)
    A Dwarf mini no longer answered on the home Wi-Fi, the official app couldn't reach it either: switched to its
    own hotspot it woke up, then joined the home Wi-Fi again (user-seen). New page /wake-dwarf, opened on the phone
    close to the Dwarf - the PC is often too far from the garden for its own Bluetooth (Force Bluetooth): over the
    phone's Bluetooth (Web Bluetooth) it checks the Bluetooth password, switches the Dwarf to hotspot mode (2.4 or
    5 GHz, not kept at the next start) and shows its hotspot's name and password; a second button sends it back to
    the home Wi-Fi (STA, the network saved at pairing) if it doesn't go back by itself, and says if its IP changed.
    Reached from Settings ("Wake up from the phone", with a QR code - the device's Settings page opened on the phone
    too); not from the watch pages, which never send anything to a Dwarf.
    Android: Chrome allows Bluetooth over http only for an address added in chrome://flags ("Insecure origins
    treated as secure") - the page says so and shows the address; iPhone: the Bluefy browser (no Web Bluetooth in
    Safari). Close the official app first: the Dwarf takes one Bluetooth connection.
  ### BugFix
    ### Full-screen live view: the running capture's image
    (user-reported Nov 2026: the image hard to see during a session, its stacked.jpg seen over FTP) The view looked
    for the capture's folder in the Dwarf's album, which lists a capture once it ended: the previous capture of the
    night was shown, or the video stream. The folder is now found over the Dwarf's FTP (there from the capture's
    start), its stacked.jpg read over HTTP, else over FTP; the album still used when the FTP can't be reached.
    ### A resumed capture no longer filed in Error when the Dwarf doesn't answer once
    (user-reported Oct 2026: the Mini's program, resumed after a network drop and a restart, filed in Error at
    30/200 at 00:45 on one state request timing out - the Mini went on to 190 images) A capture followed after a
    restart or a reconnection ends when the Dwarf says it no longer captures; no answer is no longer taken as its end.
    Silent 10 min with no new image while the connection looks open: reconnected, the follow-up resumed after it
    (the program kept in progress). A follow-up handed back by the watchdog (connection lost) now stops - it went
    on querying the Dwarf next to the resumed one, and could file the program in Error.
    ### Once the capture started, a program is never run again from its goto
    (user-set rule, Oct 2026: before the capture starts, an error may end or retry the program; once started, only
    its end, the Dwarf's stop or Stop end it) An error while following a started capture made the retries run the
    whole program again - its goto would stop the capture. Now the program stays in progress and is followed again:
    at once when the Dwarf says it still captures, filed by what it saved when it says it stopped, else after the
    reconnection. A Dwarf not answering is never taken as a capture over, at reconnection too.
    ### Reconnection tried again every 5 min while a program is in progress
    (user-asked Oct 2026: the PC running Tailscale switched off at night, 3 failed reconnections and nothing more until
    the morning - the end time, the end of capture, a low battery missed) After the 3 quick attempts, the reconnection
    is tried again every 5 min as long as a program of that Dwarf runs or waits in progress; reconnected, the capture
    is followed again, never stopped. Not when another client took the Dwarf (the official app: manual mode) or after
    a Disconnect; one Astro Dwarf Session per Dwarf, as before.
    ### Check finds the session of a program filed in Error before its capture ended
    (same night: Check of the Mini's program found nothing - its session saved at 06:00, the program filed at 00:45)
    A program in Error is looked for in the Dwarf's album up to 15 h after its start, not only up to its filing.
    ### Home screen: no Dwarf card shown since the "capture no longer moves" warning
    (user-reported Oct 2026: "No Dwarf configured yet" with one card, then "_show_stall() missing 1 required
    positional argument") The warning's method had been put between @staticmethod and the method it decorated: it
    became static and every card failed on its first refresh. Not the change of Site.
    ### Home screen: one Dwarf's card failing no longer hides the others - Connect all connects them all
    (user-reported Oct 2026: after a change of Site, one card shown under "No Dwarf configured yet") The cards were
    built one after the other and the message hidden at the end: an error on one card stopped the others, on every
    refresh. Now each card is built on its own - one that fails says so in its place, the error and its traceback in
    the log. Connect all stopped after the first Dwarf connected (a variable that didn't exist since its
    reconciliation of interrupted programs was added): the next ones were never connected.
    ### A capture ended short by the Dwarf says so - battery empty
    (user-asked Oct 2026: the Mini powered off at 6 % at 20/60, a DWARF 3 stopped at 5 % at 139/400 - the second
    read "Session completed successfully") The program's message adds "stopped by the Dwarf at 139/400", with
    "battery empty (5%)" when the battery was at 10 % or less, not charging, or a POWER OFF was received; the level
    kept in the program's file (battery_end). Not for a program stopped at its end time.
    ### A capture that no longer moves is said
    (user-reported Oct 2026: a hung DWARF 3 read "Capture in progress 141/500" all night, the same notification
    over and over - the user thought it ran) The Dwarf's card says in its header "no new image for N min - the
    Dwarf may be stuck" when the taken / stacked counts haven't changed for 10 min (or 4 x the exposure), and the log
    says it once.
    ### Connect during a capture: astro mode no longer switched
    (user-reported Oct 2026) Connect clicked at 00:20 on a DWARF 3 capturing for 3 hours sent SWITCH_SHOOTING_MODE
    (astro mode, for the live view) in the middle of the capture: the Dwarf never answered it nor any command after,
    the capture stopped at 141 images, its stacked FITS never written. The manual Connect / Reconnect and the
    dashboard's Connect all now do as the automatic connection: time, timezone and location, then astro mode only
    when nothing runs - no program here, no capture, goto or focus reported by the Dwarf.
    ### Full-screen view: "no stacked image yet" with 180 stacked
    (user-reported Oct 2026) The image was read from the Dwarf as one whole answer and kept only if it ended
    exactly as a JPEG: an MJPEG stream (never ending) or a JPEG followed by other bytes gave nothing. Now its first
    image is taken (multipart parts, with or without Content-Length, or the JPEG inside the answer), a few seconds
    at most; when none comes, the log says why (once a minute). Above all, the image is now the capture's
    stacked.jpg on the Dwarf (user-asked: as the official app and the megastack), read 3 s after each progress
    notification - the capture's folder found once in the Dwarf's album (its newest DWARF_RAW_TELE_ / WIDE_ session
    of the last 12 hours); the stream only when it isn't found, and on a DWARF II during a program.
    ### Exposure / gain refused by the Dwarf: no longer taken for a success
    A program's exposure and gain answered -1 by the Dwarf (refused) were logged "SUCCESS ... -> -1" and the step
    went on as done (user-reported Oct 2026; the values happened to be right, left by the run before). Now a refusal
    is logged and asked again once; still refused, the value read back from the Dwarf decides: already the one
    wanted, the program goes on and says so; another one, the step fails. An exposure read back in Auto is not the
    one wanted (user-found Oct 2026: a DWARF 3 stuck in Auto refused every manual exposure - the official app too -
    while its stored 15 s was read back): the step fails and says to restart the Dwarf; the camera summary warns
    when the exposure is automatic.
    ### A Dwarf of devices.json not loaded: said why
    After a reinstall, 2 Dwarfs shown out of 3 and nothing said why (user-reported Oct 2026): an entry whose
    config_*.py is missing, has no DWARF_UID, or has the DWARF_UID of a Dwarf already loaded (the second replaced
    the first) was skipped silently. It is now in the log and in a warning at the top of the dashboard, with the
    file concerned. A Dwarf whose dwarf_uid is already registered is no longer added a second time (manual
    configuration, Bluetooth pairing): the message names the Dwarf that has it.
    The cause, found by the user: Settings' Force Bluetooth, when another Dwarf answered, said "not applied" but
    had already written that Dwarf's uid and IP into this one's config_*.py - after a restart the two had the same
    uid. The file is now put back as it was when another Dwarf answers, or when the connection fails.
    ### Two Dwarfs with the same IP: said, and the other one never connected as this one
    Two configs had one IP (user-reported Oct 2026): connecting one Dwarf reached the other. Now the startup
    warning lists two Dwarfs sharing an IP; before connecting (manual, Connect all, auto-reconnect) the Dwarf
    answering at that IP is asked who it is (its HTTP deviceInfo, 2 s at most, checked again every 5 min or when
    the IP changes): another Dwarf there - not connected, the message names it and says to update the IP; a
    program doesn't start on it either. A Dwarf without that API, or not answering, connects as before.
    A Dwarf's HTTP name isn't always its uid (user-reported Oct 2026: DWARF3_3AD946 answers DWARF3_3AD246 - taken
    for another Dwarf): another Dwarf is now one answering with another registered Dwarf's uid or HTTP name, or
    with a name unlike this one's; a close name (same model, at most 2 characters apart) is kept the first time as
    this Dwarf's HTTP name (~/.astro_dwarf_session/http_names.json).
    Force Bluetooth goes to this Dwarf by its Bluetooth name (its dwarf_uid) when it is found, without a choice;
    when it isn't, it says so - another Dwarf answering alone is no longer connected on its own, and none is
    preselected in a list (user-found Oct 2026: Force Bluetooth done with the other DWARF 3 was the cause).
    ### Megastack: missing darks no longer stop it
    The Dwarf's check answered CODE_ASTRO_RESTACK_DARKFRAME_MISMATCH when dark frames are missing, and the megastack
    ended in Error. The official app only warns and lets it go on (user-reported Oct 2026): it now goes on too,
    stacked without those darks, the check step saying how many were missing.
    ### Milky Way planner: the tiles kept on one night
    The first tiles tonight, the next ones the following night (user-reported Oct 2026): the slot search ran 24 h from
    the start time, so a tile with no room left before dawn (the earlier ones up to dawn, or too low already) took a
    slot the next night, and every following tile came after it. The search now ends at the dawn of the night the start
    time reaches; a tile that doesn't fit is "not schedulable" (English and French pages).
    ### Manual positioning pad on a phone: the mount kept turning, Stop did nothing
    User-reported Oct 2026. The phone sent each press twice (touch, then its emulated mouse events), the starts and stops ran side by side,
    a start could land last; Stop was skipped while the pad believed the mount stopped. Now pointer events only, one
    command at a time in their order, Stop always sent, no long-press menu on the arrows.
    ### Programs in a row: up to 2 min 30 s lost between two of them
    When the connection check ran just as a program ended, the next program's "is the Dwarf already capturing?"
    query was sent at the same time: one answer went to the other request, and the start waited 150 s (3 of the 5
    tile changes of a Milky Way mosaic night). The next program now takes the command slot first (waiting up to
    30 s for a check in progress), then asks.
    ### Milky Way planner: tiles planned too short
    A tile was planned as count x exposure + 1 min: 24 min for 90 x 15 s, while it took ~28 min - the delay added
    up to 28 min by the 6th tile. Now counted: the dithering (the Dwarf shifts every 6 frames and loses one frame
    doing it) and ~3 min per tile for the session start, goto, waits and capture start / end.
    ### Milky Way planner: holes between the tiles
    A 3 x 2 mosaic left a hole where four tiles meet and a wedge at an outer corner: rows were laid at constant
    Dec with columns spaced by step / cos(Dec) of each row, so the columns fanned out from row to row, while the
    Dwarf frames each tile north up with straight edges - the overlap shrank to nothing at the corners. The tile
    centres are now laid on a regular grid in one tangent plane centred on the mosaic, and the grid is checked:
    every point between the tile centres must lie inside a tile with 1.5 deg to spare (the Dwarf's pointing was
    off by 1-1.3 deg); the spacing tightens until it does, and the summary says by how much. The sky chart draws
    each tile as what the camera frames (its north-up field, curved on the RA/Dec chart), no longer an RA x Dec box
    that showed the new rows as misaligned.
    The French planner's "Ou choisir un Site enregistré" read "enregistr\u00e9" (and the empty Site choice "\u2014"
    on both): escapes written in the page's HTML, where they are not decoded.
    ### Executable: "No module named 'qrcode'" (QR codes of Watch mode / wake-up)
    The app ran from Python but the rebuilt executable failed: nicegui-pack calls, on Windows, the first
    "pyinstaller" on the PATH, possibly another Python install's, which leaves out silently a module it can't
    find. buildAstroDwarfUI.py now runs PyInstaller with its own Python (nicegui-pack's arguments), first
    checks that every requirement and PyInstaller are installed there (else stops with the pip command), and
    names qrcode / qrcode.image.svg as hidden imports (imported inside a function).
    On macOS it also checks Pillow (PyInstaller turns the .ico into an .icns with it - the CI workflow installs it).
    ### Autofocus refused after the Dwarf restarted (CAMERA_TELE_CLOSED)
    The Dwarf powered off and back on (user log, Mini): this app reconnected on its own, but only the first
    connection since its start entered astro mode - the camera stayed closed until a manual Reconnect. An automatic
    reconnect now enters astro mode too when nothing runs (no program here, no camera / motor / focus operation on
    the Dwarf): a capture going on through a network drop is left alone.
    ### A megastack running on the Dwarf (started by the official app, even closed since)
    The Dwarf can do nothing else meanwhile: a program started then failed on its first commands. Known now from the
    Dwarf's task state (sent with each device state, dwarf_python_api 3.1.6): a due program waits in ToDo and starts
    after it (a manual start, a megastack asked meanwhile: refused with the reason), the end of the night does
    nothing (above all no power off in the middle of it), and the device card shows "Megastack running on the
    Dwarf" with its progress (as above).
    ### A program reopened in the editor kept its old date
    A result reopened with the pencil (to capture its target again) kept the date of its first run: easy to miss,
    the program then ran at once whatever its time. Opening a program whose date/time is past now moves the date
    to the next occurrence of its time (the time is kept), with a notice.
    ### A resumed capture stopped hours before its end time
    After a reconnection the app resumes following the program the Dwarf is capturing. Its end time was taken from
    the program's scheduled date: a program run again from an older file (dated the day before) found "end time
    06:40 reached" at 03:22 and stopped the capture. It is now taken from the program's actual start, and an end
    more than 12 h past is never this run's (the next one is).
    ### View / Check showed nothing on the Programs page
    The Results tab's View / Check dialog was inside the list it refreshes when the result comes in: it vanished
    before showing anything. It now opens on the page.
    ### The same run in Done and in Error after a network drop
    A connection lost during a program marked it failed (Error), then the reconnection resumed following the
    capture and recorded it again (Done). The interrupted program now stays in Current until the reconnection
    resumes it: one result, Done or Error depending on how the capture ends.
    ### Initial position not saved after a calibration
    A calibration doesn't always reset the Dwarf's motors: reading the position after it answered NEED RESET and
    nothing was saved. Before a program's EQ Solving and calibration (before the EQ when there is one: a reset after
    it might shift what it measured), the axes are now reset when the Dwarf doesn't give its position (each axis
    goes to its limit and comes back where it was) - not with a bulky accessory mounted.
    The Actions' EQ Solving does the same before the EQ (an EQ done by hand, in several iterations, before a program:
    the program then finds the axes referenced and resets nothing after it).
    Going to the initial position (a program's start position, the Actions) resets the axes only when the Dwarf
    doesn't give its position (switched off since), and moves nothing when it is already there (within 1 degree) -
    it reset them at every start, even right after "Save position".
    ### A manual capture left the last program's steps shown
    Starting a capture from the Actions (or the official app, or the Dwarf's own schedule) left the last program's
    steps and result at the bottom of the device page. They are cleared when such a capture starts.
    ### End of the night card: the estimated time
    A program without an end time counted as ending at its START ("end of the night around 21:17, last planned
    activity until 21:15" for a program starting at 21:15). Its end is now estimated: 5 min of preparation (start
    position, focus, EQ, calibration, goto) + count x exposure. The program running counts too.
    ### A program's start showed the previous capture's counts
    "1/13" shown for a moment at a program's start, then 0/0: the client kept the last capture's counts until the
    new capture's first progress. Reset when a program starts.
    ### "Client has been deleted but is still being used" on a device page
    The page refreshed every 2 s after its connection check, which can take a few seconds - when the page had been
    left or reloaded meanwhile (or an action ended after it), NiceGUI warned with a long stack. Not refreshed then.
    ### Catalog, Program session to the Dwarf: unticking a target left out another one
    The panel's rows were matched to their targets by position, while the tasks are sorted (the target that sets
    first goes first) and those without RA / Dec dropped: a row could show M 33 and untick M 31 (user-found Oct
    2026). Each task now carries its target's id (planId, already sent with the schedule).
    An unticked target also vanished from the list, so it couldn't be ticked again (nor anything, once all were
    unticked): it stays, greyed, "left out" - tick it again to put it back.

## [3.2.5] - 2026-10-16
  ### BugFix
    ### A capture finished while the app was stopped is no longer put back in ToDo
    The app stopped during a capture (a Windows update at night) and restarted after the Dwarf had finished: the
    program left in Current/ was put back in ToDo as pending, as if never run - it would have been captured again.
    Now, when its capture had started and the Dwarf no longer captures, how it ended is read from the Dwarf's album
    (its session of that target, images taken and stacked - as "Check on the Dwarf"): to Done when it reached the
    count asked, to Error when it stopped before (clouds, battery...) or stacked nothing. When the album can't tell,
    to Done marked "its end was not followed". Only a program stopped before its capture started (goto,
    calibration...) is put back in ToDo, as before.
    Also checked when the Dwarf, off when the app restarted, is connected later from its device page (only the
    dashboard's Connect all and the automatic reconnection did it).

## [3.2.4] - 2026-10-13
  ### Add
    ### /api/app-info
    GET /api/app-info answers {"app": "astro_dwarf_session", "name", "version"}: Dwarfium-Hub tells this app from
    another program on the same port, and learns the version of an installation it didn't install.
    ### Manual configuration filled in by Dwarfium-Hub
    The manual configuration page takes ?name=&model=&ip= (filled in) and ?dwarfium_id=&dwarfium_base_url= (the new
    device is saved linked to that Dwarf of Scope Archive): Dwarfium-Hub opens it to add a Dwarf Scope Archive
    already knows.
    ### Manual configuration from the IP alone
    "Read from the Dwarf" next to the IP fills in the UID (the Dwarf's Bluetooth name) and the model from the Dwarf
    itself (POST :8082/deviceInfo - only these two fields are kept, the passwords in that answer are never kept nor
    logged); done on save too when the UID is empty, and on opening when the page is given an IP (Dwarfium-Hub).
    The UID can still be typed in when the Dwarf isn't reachable.
    ### Identify a Dwarf
    Its ring light flashes 3 times, to tell which Dwarf it is when several are on: a button on each device card and
    next to the IP of the manual configuration, and GET /api/identify?ip= (Scope Archive's Dwarf page, Dwarfium-Hub's
    Dwarfs tab). Never during a capture: refused when a program runs on it, a photo is being taken, or its state shows
    a camera / motor / focus operation (a native schedule running on the Dwarf too). The light ends as the Dwarf
    reported it before (its rgb_state, on when unknown - a Dwarf's ring light is usually on). A Dwarf already
    connected uses its own connection and command slot; otherwise a short connection of its own, closed afterwards -
    refused, not forced, when another app (DwarfLab) holds the Dwarf.
    ### Pages opened in this app's window
    POST /api/open-page {"path"} (this computer only) shows a page of this app where it is open on this PC (its own
    window, or a local browser tab): Dwarfium-Hub opens the manual configuration and the pairing there instead of in a
    new browser tab, and brings this app's window to the front (Windows: plain Win32, as Dwarfium Scope Archive does).
    Plain page navigation, never the window's own methods (whose answers can hang). {"shown": false} when no page of
    this app is open here.
  ### BugFix
    ### Lights and power light: the Dwarf's own state
    Toggle lights and toggle power light read the light's state as the Dwarf reports it before sending a command (its
    RGB / power indicator notification, else rgb_state / power_ind_state in the device state on connection), the
    state remembered after this app's own commands being only a fallback: a light switched elsewhere (the DwarfLab
    app, the Dwarf itself) or on from the start no longer needs two clicks.

## [3.2.3] - 2026-10-11
  ### Add
    ### Dwarfium Scope Archive presence
    This app now says hello to Dwarfium Scope Archive (the URL of the Settings page) at startup and every 30 s
    (every 10 s while it doesn't answer). Scope Archive thus knows this app's address, to offer actions done here, and
    this app knows whether Scope Archive is running: its "Open in" / "Archive" buttons are greyed when it isn't, and a
    click then says so at once instead of waiting for a timeout and opening a dead browser tab. Logged when it changes.
    ### Plan a target page, opened from Scope Archive's Recommended tonight
    New page /plan-target (plan_target.html, English / French with the app's language): one target with its best slot
    tonight, given in the address by Dwarfium Scope Archive's "Recommended tonight" page (its button on each target).
    Pick the Dwarf, send as a program of this app (Programs page, run when the Dwarf is armed) or as a native schedule
    on the Dwarf, the slot, camera, exposure, gain, filter and autofocus, then send. The choices are remembered.
    With Scope Archive's "tonight's plan" (up to 5 targets), the page chains them over the night: the first to set
    first, each slot within its window, the night shared between them, 5 min apart; slots editable, untick a target
    to leave it out (the others re-flow). Sent as one program per target, or one native schedule with all of them.
    Each target has its own exposure, gain and filter, prefilled from the Capture card (now the defaults for every
    target): changing a default updates the targets not changed by hand; ↺ puts a target back on the defaults.
    Camera and autofocus stay common. Exposure, gain and filter lists only offer the values the chosen Dwarf accepts
    (e.g. no 20 s; 180 s on the Mini only; VIS on the Dwarf 3 only); changing the Dwarf moves a value it lacks to the
    nearest one below.

## [3.2.2] - 2026-10-09
  ### Add
    ### Catalog: mosaic planner for the Dwarf 3 / Dwarf Mini
    The catalog's Mosaic Planner (/catalog) only offered ASIAIR rigs. A "Planner" choice at its top now switches to
    the Dwarf planner (js/renderMosaic_dwarf.js, now loaded): a paired Dwarf, Wide or Tele field, a grid of tiles
    and/or the Dwarf's own mosaic (framing 1.0-1.8 per axis, up to 2x2 panels), exposure / gain / images per panel,
    the night's schedule from the site (the catalog's active location by default), and "Send to Dwarf", which creates
    the programs here. The ASIAIR planner is unchanged; the choice is remembered.
    ### Catalog: my own Dwarf list (up to 5 objects)
    Each object's detail pane in the catalog gets a "+ Dwarf list" button. A "Dwarf list (n/5)" chip opens the list
    (remove an object, clear) and "Program to the Dwarf": the objects are planned for tonight at the active site like
    the Best-of-Tonight plan (usable window, filter, exposure / gain for the Dwarf rig) and sent through the same
    "Program session to the Dwarf" panel. Objects not usable tonight are named and left out.
  ### BugFix
    ### FFmpeg missing: said in the log file and on the device page
    Without FFmpeg the RTSP live view can't work. The message saying so went to the console only: not in
    astro_session.log, and nowhere with the .exe. FFmpeg is now checked at startup, the message is written to
    astro_session.log, and the device page shows it (with the download link) where the RTSP live view would be.
    ### Catalog: 80 s exposure suggested for a Dwarf
    "Best of Tonight" / Imaging Settings could suggest 80 s for a Dwarf 3 or Dwarf Mini, a value the Dwarf doesn't
    offer (its list goes 60, 90, 120...). The catalog's exposure lists for both now match the Dwarf's.
    ### Catalog Dwarf mosaic: tiles scheduled in daylight
    The Dwarf mosaic planner only checked the target's altitude, so a target high only in daytime got a tile the next
    morning (e.g. 08:45). Tiles are now placed inside the site's dark window of that night (as Best of Tonight
    computes it), each ending before dawn; the header shows that window, and a tile with no room is "No slot tonight".
    ### Catalog Dwarf mosaic: grid sized to the target
    The grid kept the last columns x rows (e.g. 3x5 for any object). For a new target the grid is now the smallest
    one covering the object's catalogue shape (+10% margin) with the chosen field, native mosaic and overlap; the
    Mosaic grid card shows the target size, the fitting grid, and a "Fit to target" button after a manual change.

## [3.2.1] - 2026-10-08
  ### Add
    ### Archive in Dwarfium Scope Archive from a remote site
    The links to Scope Archive now give it the Dwarf's IP as this app reaches it (Scope Archive at home, this app on a
    remote site with the Dwarf reached through Tailscale): its import and Transfer pages try it first for FTP, and
    its Dwarf Configuration page ("Config" link) offers to save it as FTP IP or as session IP - a second IP it
    keeps for this Dwarf, using whichever answers. Requires Dwarfium Scope Archive V3.4.0; older versions ignore it.
    ### Languages: add one without changing the code
    Languages are now found at startup from components/locales/ (as in Dwarfium Scope Archive): each locale file
    declares LANGUAGE_NAME and ENABLED, and a language is offered once ENABLED = True. With more than two, the home
    page's EN / FR button opens a menu of the enabled languages. `python tools/check_i18n.py --new <code> "<name>"`
    writes a template from English (values marked # TODO, ENABLED = False). With the packaged app, the locale files
    next to the executable are read first, so a translator can test without Python. The Program page and the mosaic
    planner fall back to English for other languages (they fell back to French).
  ### BugFix
    ### RTSP live preview: recent FFmpeg, recovery after another client
    With FFmpeg 5 or later the embedded RTSP preview never started: its -stimeout option no longer exists. The app now
    asks the installed FFmpeg once and uses -timeout (FFmpeg 5+) or -stimeout (FFmpeg 4). The preview also comes back
    reliably after another client (e.g. the phone app) takes the stream over: a stalled stream no longer blocks the
    worker, it reconnects with a growing pause (1 s to 10 s) while the Dwarf refuses it instead of retrying
    back-to-back, and a Stop immediately followed by a Start no longer leaves the preview stopped.
    ### RTSP live preview: no more reconnect every 25 s
    The RTSP preview reconnected to the Dwarf every 25 s even when everything worked (a leftover from the OpenCV
    era): a short freeze each time, and a new RTSP session that could take the stream back from the phone app or
    lose it. Now off; a stream that really stops is still reconnected after 8 s without images. For comparison the
    old behaviour can be turned back on with the environment variable ASTRO_DWARF_RTSP_RESPAWN_S=25.
    ### Auto-connect at startup: astro mode entered
    The automatic connection at app startup only set the time, timezone and location: the Dwarf never got the mode
    switch / camera opening the Connect button sends, so no RTSP live view until a manual Disconnect / Connect. The
    first automatic connection since startup now enters astro mode too, unless a program runs or the Dwarf reports
    something in progress (capture, goto, tracking, calibration, autofocus), so as not to disturb it. Reconnects
    after a drop stay light, as before.
    ### RTSP live preview shown on several pages / devices
    The live view of a camera is shared by every page showing it (app window, PC browser, phone browser), but closing
    any one of them stopped it for all: the other streams froze and stayed frozen, even after that page came back,
    until they were reloaded. The stream now stops only when the last page showing it closes or collapses it.
    ### Dwarfium Scope Archive starting: "try again" instead of a browser tab
    While Scope Archive's window is still starting, it answers "busy" (Scope Archive V3.4.0 with its home-page ready
    signal): "Archive" and the device page links then show a message asking to try again in a moment, instead of
    opening a browser tab.
    ### Device page actions: label under its icon
    On a wide screen "Toggle Power Light", a bit too long for its column, went under its icon; the action buttons now
    keep the icon and label on one line (cut with "…" if needed).

## [3.2.0] - 2026-10-06
  ### Add
    ### Archive a session with Dwarfium Scope Archive
    The session explorer's large view, the View / Check dialog and the Program page get an "Archive in Dwarfium Scope
    Archive" button: Scope Archive's import page reads and registers this session only from the Dwarf (after saying
    if it is already backed up), then opens its Transfer page with it preselected, where the backup drive is chosen
    and the copy started. When Scope Archive runs as an app the pages open in its own window, brought to front, with
    its system folder dialogs; otherwise (browser / server mode, not running, older version) in a browser tab.
    The device page's links become "Dwarfium Scope Archive: Config · Sessions on the Dwarf · Backed-up sessions",
    opened the same way. Shown when the Dwarfium Scope Archive URL and Dwarf Id are set in Settings (labels renamed
    from "Dwarfium"). Requires Dwarfium Scope Archive V3.4.0.
    ### What the Dwarf saved: View / Check
    Native schedule tasks get a "Check" button when failed or interrupted (red; orange for error -1) and a "View"
    button when successful (blue): the task's session is found in the Dwarf's album (target name + time window) and
    its shotsInfo.json read - images stacked / taken, integration time, stacked thumbnail. Error -1
    (WS_PARSE_PROTOBUF_ERROR, the window ending while the stack is usually saved) is shown as an orange "Warning"
    instead of a failure with its protobuf name. The same dialog is on the Programs page's Results tab and the Program
    HTML page, also for this app's own finished programs (their target and real start / end). What it finds is kept
    (task_check_cache.json) and the images stacked / taken then show directly in the lists, refreshed as soon as a
    check is done from any page. One album listing and one small JSON over HTTP, on click only.
    ### Session explorer: download the stacked image
    The explorer's large view gets a JPG / PNG download menu: the session's stacked.jpg, and the Dwarf's own PNG
    ("stacked-16_M 42 ..._Duo-Band_...png", looked for in the session folder over the Dwarf's anonymous FTP, offered
    only when present). In the native window the app writes the file itself after the system Save dialog (Downloads
    folder if it can't open) and shows the path; in a browser, the browser's download.
    ### Device page: Shut down button
    At the right of Disconnect, a "Shut down" button powers the Dwarf off after a confirmation
    (CMD_RGB_POWER_POWER_DOWN), then closes the connection as a manual Disconnect so the app doesn't reconnect to it.
    ### Preview: stacked image / last frame
    The device page's camera previews get a "Stacked / Last frame" switch, the official app's own toggle
    (displaySource parameter, 1 stacked, 0 last frame). The current choice is read from the Dwarf's HTTP API once it
    is connected ("Stacked" when the parameter was never set). Usable during a program's capture.
    ### Current target on the dashboard and the watch page
    The dashboard card and the watch page (/watch/<device>) now show the target being shot: the goto target of
    the program run by this app (also in the "program in progress" banner), or the native shooting schedule task
    run by the Dwarf itself ("Schedule <name> · <target>", task n/total and its time window, in the device's
    timezone), also before its capture starts (goto, calibration). The schedule list is read from the Dwarf only
    when a capture starts outside a program of this app - never polled otherwise. Any other capture (another app, by
    hand...) shows the target name the Dwarf itself sends in its notifications. Requires dwarf_python_api 3.1.5.
    ### One instance per Dwarf on this PC
    Two Astro Dwarf Session open together (e.g. the .exe and a source run) on the same Dwarf took it from each other
    in turn. The first instance to connect now holds the Dwarf (lock file in the temp folder, released on
    Disconnect, on exit or after a crash); the other one doesn't connect, its card says the Dwarf is used by another
    instance with an "Open its view" link to that instance's watch page, and it connects by itself once the Dwarf is
    free. A Dwarf that drops the connection right after each reconnection (3 times within a minute) is being used
    by another client - a Dwarf Mini accepts only one connection: auto-reconnect then stops instead of taking it
    back in a loop, and the card says so until the user connects again.
    ### Hide a Dwarf on the dashboard
    The eye button on a card hides a Dwarf not used for now: only its header (name, IP, status) stays, it moves after
    the others, and it isn't auto-connected. The same button shows it again. Saved in device_prefs.json.
    ### Dashboard order
    The ⇅ button on a card moves it first, up, down or last (hidden Dwarfs stay after the others). Saved in
    device_prefs.json; the watch dashboard (/watch) shows the same order and hidden Dwarfs.
    ### Force the resume of a program in error
    Programs page, Results: a failed run shows its error date, and a "Force resume" button when the Dwarf is still
    capturing that program's target and the error is less than 15 h old. It moves the file back to Current/ and
    runs the normal resume, end time included.
    ### Program page: newest first and "Show more"
    The "All" filter lists the newest rows first, 20 at a time, with a "Show more (n left)" button. "Future" is
    unchanged.
    ### Version on the home page
    The app's version is shown small on the home page, at the left of the "Dwarfium Lite" line (from version.py
    when built, else from CHANGELOG.md).
    ### Lights during a program
    The two light buttons (light, power indicator) now work while a program captures, like the preview switch: the
    run only reads the Dwarf's status then, so the command no longer waits for the program to end. In the program's other
    steps (goto, calibration...) they still say the device is busy.
  ### BugFix
    ### Manual goto: RA / Dec in hours-minutes-seconds
    The program editor only read decimal RA / Dec: "18h 13m 40.3s" / "-17° 36' 06\"" was saved EMPTY, without a word,
    and the goto had no coordinates. Both fields now take decimal values or the usual notations (18h 13m 40.3s,
    18:13:40.3, 18 13 40.3, -17° 36' 06", -17:36:06, -17d36m06s; a decimal RA above 24 is read as degrees) and save
    decimal hours / degrees; an unreadable value is shown in red and blocks the save. The runner reads the same
    notations, with the Dec sign applied to the whole value.
    ### Device page: clicks sometimes ignored
    The page rebuilds its main view every 2 s; a click landing during a rebuild hit a button just replaced and was
    lost. The view is no longer rebuilt right after a press on the page (1.5 s); its dialogs stay open across that
    refresh and their notifications are shown.
    ### Native schedule editor: end time instead of image count
    A task's window was count x exposure + 2 min: too short for the goto/calibration and per-frame overhead, so it
    ended before the last frames and the Dwarf reported an error although the stack was saved (DwarfLab's
    analysis). Like the official app, the editor now takes a start and an END time (across midnight allowed); count
    is sent as 0. It also shows the native tasks already on the Dwarf that are upcoming or running (read again
    automatically when older than 10 min), refuses a new target overlapping them (5 min gap) and draws them on the
    altitude chart. Default slot: now + 5 min, or right after the running and chained tasks (+ 5 min), 1 h long;
    "Next free slot" applies the same rule.
    ### Milky Way mosaic planner: tiles scheduled in daylight
    Tiles were scheduled on altitude alone, so at dawn and after sunrise too. A slot must now be dark for the tile's
    whole duration (new "Darkness" setting: Sun below -18/-12/-6°, astronomical night by default); the default start
    time ("now") no longer rolls the plan to the next day.
    ### No more "slot busy" flood during a program
    While a program holds the device, the connection health check is skipped instead of being denied and logged on
    every poll tick of every open page.
    ### Target of a program run by this app
    The dashboard card and the watch page showed no target for a program run by this app: its goto target was read
    from the wrong part of the program. Fixed, with the target name the Dwarf sends as a fallback.
    ### Program followed again after a restart
    A program left in Current/ by an app restart during its capture was only resumed if its last step was less than
    5 min old. It is now resumed when the Dwarf reports capturing the program's target, or, while that name isn't
    known yet, when the last step is less than 15 h old - never when the Dwarf reports another target. Its end time
    is applied again while resumed.
    ### "Use best slot" (program editor)
    A best slot whose start has already passed now starts 5 min from now (also in the native schedule editor); a
    slot already over is refused. The image count is set to fill the slot (it stayed at its default, 20, so the
    program stopped long before the chosen end time).
    ### Program files: occasional "Invalid JSON file"
    Program files (ToDo / Current / Done / Error) are now written to a temporary file then swapped in, so a read at
    the same moment (Programs page, scheduler, a run updating its status) never finds one empty or half written.
    When a file can't be read, the message now says why: no longer in the queue (already started, moved or deleted)
    or the JSON error itself.
    ### EQ Solving indicator inverted on the Dwarf 3
    The EQ Solving result panel (which way to turn the azimuth / altitude knobs) used an inverted mapping on the
    Dwarf 3 and Dwarf II. All models now share the Mini's convention, the right one on the D3 as well.
    ### Preview switch: occasional "device busy"
    The Stacked / Last frame switch now takes priority over the periodic connection check, like the action buttons.
    ### Dwarfium Scope Archive settings not kept
    The Settings page saved the Dwarfium Scope Archive URL and Dwarf Id to the device's config.ini, but they weren't
    read back at the next start (dwarf_python_api's DwarfConfig had no such fields): the links were gone after each
    restart. They are now read from config.ini (dwarf_python_api 3.1.5 reads them itself).

## [3.1.6] - 2026-10-04
  ### BugFix
    ### Port detection
    Launched one after the other, this app and Dwarfium Scope Archive could pick the same port on Windows (a free test
    bind on 0.0.0.0 doesn't see a server listening on 127.0.0.1). A port is now free only when nothing answers on it and
    it binds on 127.0.0.1, 0.0.0.0 and the --host address (exclusive bind on Windows).

## [3.1.5] - 2026-10-04
    ### New features
    ### Program editor: target catalog + altitude planner
    "Pick from catalog": choose a target from the DSO catalog shared with Dwarfium Scope Archive
    (Messier, NGC, IC, Caldwell, bright stars), next to "Get from Stellarium". Search by name, filter by
    type and by the highest altitude reached in the dark on the program's night.
    The catalog is read from a Dwarfium Scope Archive install next to this app (or $DWARFIUM_ARCHIVE_DIR)
    when present, otherwise from assets/dso_catalog.json (loose file next to the exe, replaceable).
    "Altitude in the sky / best slot": the target's altitude over the night with the Sun and Moon,
    darkness level (astronomical/nautical/civil) and minimum altitude settings, the best slot highlighted;
    "Use best slot" fills the start date/time and the end time, a click on the curve sets the start time.
    ### Catalog add-on: targets sent from /catalog
    When "Keep these targets in astro_dwarf_session's catalog" is ticked in the /catalog page's send window
    (off by default, the choice is remembered), the targets sent to a Dwarf are added to a second file,
    catalog_add_on.json, next to the dso_catalog.json in use (Dwarfium Scope Archive's db/ when installed
    next to this app, else assets/), when they are not already in the shared catalog (same designation,
    or within 2'). They then show up in "Pick from catalog" like the others (Sharpless, LDN, LBN, vdB,
    Hickson...). Same schema as dso_catalog.json (plus "source" and "addedAt"); dso_catalog.json is never
    modified, and Dwarfium Scope Archive can import catalog_add_on.json after it with the same importer.
    An added object can be removed again with the bin icon on its row in "Pick from catalog".
    ### Native shooting schedule: same catalog + altitude planner
    "Pick from catalog" and the altitude chart are also in the native schedule editor, in the device's
    timezone like the rest of that form. Targets already added are drawn on the chart (red) so the next one
    can be fitted around them. "Use best slot" sets the start; duration stays count x exposure, with a
    warning when it runs past the end of the slot.
    ### Site timezone everywhere (remote setups)
    Program date/time and End time are now wall-clock times of the Dwarf's SITE (its configured timezone,
    written from the Site), no longer of the PC running the app: the scheduler starts programs, stops at
    End time, stamps realStart/realEnd, and the editors/APIs fill their defaults with the site's clock.
    Same timezone as the native schedule. Falls back to the PC's timezone when none is set (unchanged
    behaviour), so nothing changes when the PC and the site share a timezone.
    /api/program accepts startEpochMs/endEpochMs (absolute instants, converted to site time); the Milky Way
    mosaic planners send them, so a browser in another timezone (e.g. remote access over Tailscale) schedules
    at the right time. The plain date/time/endTime fields are still accepted.
    ### Altitude chart: compass direction of the target
    The target's direction (N, NE, E, SE, S, SW, W, NW - in French N, NE, E, SE, S, SO, O, NO) is labelled
    on the curve each time it changes while the target is above the horizon, shown in the tooltip with the
    azimuth (e.g. "S (187°)") and in the summary ("Highest at 00:45 (36°, S)") - to see when the target is
    behind trees or a house on one side. Program editor and native schedule editor.
    ### Improvements
    ### Target picked from the catalog
    Short target name, as Dwarfium Scope Archive shows it: the catalog name up to the first comma
    ("M 42 - Great Nebula in Orion, Great Orion Nebula,Orion Nebula" -> "M 42 - Great Nebula in Orion"),
    also used in the program description.
    ### Mobile layout
    Target row (program editor and native schedule editor): on a phone the target name gets its own
    full-width line instead of being squeezed between RA and Dec; RA/Dec are narrower and stay together
    on the next line. Unchanged on desktop.
    ### Native shooting schedule: failure reason
    The error code recorded by the Dwarf for a failed or interrupted task is now shown next to the task,
    in the session page's Shooting Schedule section and on the Programs page (e.g. "-16310
    SHOOTING_SCHEDULE_INTERRUPTED" when the Dwarf was off or unavailable at start time, "-11504
    ASTRO_CALIBRATION_FAILED"), instead of only in the official mobile app.
    ### Native window
    The native window (pywebview) no longer runs in private mode: its browser storage (language,
    remembered choices) is kept between launches.
  ### BugFix
    ### Device clock set on every connection
    The native schedule runs on the Dwarf's own clock, but the app only set it when a local program
    started: a Dwarf connected through the UI kept whatever clock it had, and valid schedules were
    rejected with -16301 (INVALID_SHOOTING_DURATION) until the official app had been opened once.
    Time, timezone and location are now sent on every connection, as the official app does: manual
    connect, automatic connection at startup and reconnects (opened with SET_TIME itself, ~5 s instead
    of ~11 s).
    Requires dwarf_python_api 3.1.4 (also sets the clock on any new connection, and logs the Dwarf
    clock offset on each schedule sync).

## [3.1.4] - 2026-10-02
    ### Improvements
    ### Native shooting schedule
    Times entered in the schedule editor use the device's configured timezone (falls back to the PC's
    timezone when empty or unknown) for defaults, "Now + 10 min", the UTC conversion and the read-back display.
    Schedules starting more than 12 h ahead are no longer refused: they are stored as pending and synced
    automatically once within 12 h of their start (app running, Dwarf connected and idle).
    The pending banner shows the auto-sync time.
    Targets must not overlap: 5 min minimum gap, enforced in the editor (with the next free slot
    pre-filled) and in the catalog page's slot planning (which also never starts a slot in the past).
    Schedule/task ids follow the official app's format; createFrom = 2 (manual entry).
    ### Misc
    Schedule debug output now goes to log.debug.
    Requires dwarf_python_api 3.1.2 (protobuf >= 7.35.1).
  ### BugFix
    ### Native shooting schedule (device-tested)
    Fixes CODE_SHOOTING_SCHEDULE_INVALID_SHOOTING_DURATION (-16301): task windows are sent in
    whole minutes, aligned on :00 (the extra 5 s on the end time is removed), matching the official app.

## [3.1.3] - 2026-09-30
    ### Improvements
    This change adds native Tele mosaic handling across the app: parsing of setup_camera framing/mosaic_count values in the API, updated scheduler and watch views to surface mosaic state, and new JS modules that build and send Dwarf schedule payloads.
    It also exposes mosaic metadata in the program list, adds static JS serving for the browser code, and updates locale strings used by the capture status banners.

## [3.1.2] - 2026-09-27
    ### Improvements
    This commit normalizes the no-native CLI flag to --no_native
    Updates the README example and App Screenshots
    Adds clearer shutdown handling for KeyboardInterrupt/SystemExit.
    It also adjusts the native window sizing
    Updates the French program page heading to match the current naming.

    Add Dwarfium Lite branding to dashboard
    ### Bug
    Fix headless mode and UI startup

## [3.1.1] - 2026-09-26
    Adds a combined "Programs" page (/Program-fr, /Program-en) showing, per
    device and merged into a single time-sorted list, both astro_dwarf_session's
    own local programs and the device's native on-device shooting schedule -
    tagged Local/Natif so the two sources stay distinguishable.
    A Tous/Futur filter (Futur by default) hides already-past entries; local
    programs now include their Done/Error history too, not just what's still
    pending, with each entry's real run start/end time (not just the originally
    scheduled one) shown once it has actually run.
    A small icon on the per-device Programs page opens this new page for that
    device, in the app's current language.
    Adds a persistent JSON-backed cache for the native schedule read, so it's
    still shown (marked as cached) even when the device is offline or busy.
    Also fixes a KeyError crash in the existing Shooting Schedule UI caused by
    that same cache being written in two slightly different shapes by two
    different callers.

    Key changes:
        - components/native_schedule.py (new): shared native-schedule parsing
          and its persistent cache (native_schedule_cache.json).
        - components/scheduler_loop.py: list_upcoming_programs() (ToDo/Done/
          Error, with scheduled/actual start-end times) for the combined view.
        - components/api_routes.py: new GET /api/programs, GET /Program-{lang}
          (/{dwarfUid}) routes.
        - pages/session.py: Shooting Schedule UI now shares the same cache/
          parsing instead of its own now-fixed in-memory copy.
        - program_fr.html / program_en.html (new): the combined page itself.
        - pages/programs.py, components/locales/{fr,en}.py: the new launch icon
          and its tooltip translation.
        - buildAstroDwarfUI.py: bundles program_fr.html/program_en.html into the
          packaged exe.

## [3.1.0] - 2026-09-25
    This change adds orphaned Current/ reconciliation during reconnect and connect-all flows.
    It re-queues stale interrupted jobs back to ToDo
    Resumes valid interrupted captures using fresh device status checks, and finalizes orphaned files to Error when no active capture matches them.
    The patch also writes last-step metadata to the current program state for better recovery, and fixes the Wide camera retry path in the session flow so resumed captures are tracked correctly.

## [3.0.9] - 2026-09-25
    WIP - Improve stop and reconnect handling
    This change shortens the stale-run watchdog grace period and ensures disconnected sessions quickly release command slots so auto-reconnect can resume.
    It adds stop-request tracking to run state and the UI so the program panel shows a clear 'Stopping...' state while capture shutdown is in progress.
    The astro capture wait loop now checks for stop requests even when no scheduled end time is configured, and the retry logic stops the device immediately instead of waiting for a stale blocking call to finish.
    It also guards against late stale results overwriting forced-failure states.

    Add manual-disconnect suppression and reconciliation so a user Disconnect isn't immediately auto-reconnected and force-stopped runs can be corrected if the device finished while offline.
    Key changes:
        - components/connection_health.py: track manual disconnects; skip auto-reconnect when set;
          call reconcile_after_reconnect after successful reconnect.
        - components/scheduler_runner.py: extend RunState (program/current_path/last_saved_path),
          ensure force-stopped runs are moved to Error,
          implement reconcile_after_reconnect to upgrade Error->Done when device confirms completion,
          stash/restore shot counts.
        - dwarf_session.py: confirm device stop via status polling.
        - pages/session.py: mark manual disconnect on UI Disconnect.


## [3.0.8] - 2026-09-24
### Improvements
    Updates the modern IR filter API and capture behavior
    Adds saved-site lookup for Milky Way mosaic planner
    Exposes manual IP updates in settings no bluetooth needed
    Improves monitoring labels for battery charging and running state.

### Bug
    This patch fixes command-slot race conditions between periodic health checks and scheduled/manual actions
    Correct fatal bug during testing the D2 
    A watchdog now force-cleans stuck runs
    UI labels were corrected

## [3.0.7] - 2026-09-21
### Improvements
    Add a replaceable Milky Way mosaic planner (English + French HTML) and a small API test page
    Wire a new /mosaic-planner-{lang} route that serves the planner from next to the running exe via _external_path
    Copy those files into dist during build (warn if missing).
    Also add related i18n keys (en/fr) and a Programs-page button that opens the planner for the app language.
    This lets the planner be updated without rebuilding the exe.

## [3.0.6] - 2026-09-21
### Improvements

    Add shared logic to pick the active camera and surface run metadata to the UI.

    Add scheduler_runner.resolve_active_camera_is_tele(...) to prefer RunState (with a safe device-status fallback) when choosing Tele vs Wide.
    Use the resolver in camera_stream and device_card to pick correct stacking URLs and capturing labels; fix early-return and status checks in camera_stream.
    Include count_info and mosaic_info on id_command in scheduler_runner._run_blocking so program list can show run targets.
    Render count and mosaic details in pages/programs.
    Report brief progress_callback messages after setting total and mosaic counts in dwarf_session.

    These changes ensure a single source of truth for camera selection and expose run targets to the UI for clearer user feedback.


## [3.0.5] - 2026-09-20
### Improvements
    This update refines the app’s visual structure with card-based panels, improved contrast across the page shell, and cleaner action layouts. 
    It adds a Go Live action, reorders focus/calibration controls, and fixes the EQ altitude direction logic. (To be confirmed)
    The program editor now shows estimated total duration based on exposure and frame count, including the end-time behavior.
    Explorer views also fetch and display shotsInfo metadata for stacked counts and total exposure duration.
    Additionally, camera, stream, motor pad, and settings sections were wrapped for a more consistent card-based UI.

    This changeset adds a new /api/program API for saving and optionally starting manual target programs, including Wide/Tele camera configuration and auto-device resolution.
    It also expands the device snapshot payload with model/IP metadata, 

### Bug
    fixes run-state detection during active program execution,
    corrects camera thumbnail selection for Wide stacks,
    updates the PWA manifest/icon to a valid square image for Android installability.

## [3.0.4] - 2026-09-19

### Improvements
    Multiple enhancements and fixes: publish LAN port and use a robust find_open_port()
    Add network_info (local IP, LAN port, watch URL/QR) and show QR/URL on dashboard and logs
    Support virtual "Any <model> (auto)" devices and auto-resolution when scheduling
    Add power-indicator toggle and i18n strings
    Visual low-battery/low-disk warnings on cards and session metrics
    Add QrCode to Start a Watch Only Stacking Session
    Add qrcode to requirements.

### Bug
    fix build script to bundle catalog.html and resolve bundled path in API routes
    fix scheduler/health-check race with start_pending flags;

## [3.0.3] - 2026-09-19

### Improvements
    New /watch read-only dashboard and per-device spectator pages
    New site-based setup flow and manual Wi-Fi configuration path
    Add on-device shooting schedule management
    Better date/time pickers
    Optional capture end times for Manual Programs
    Dashboard improvements for last-run status, connect-all actions, and richer capture progress reporting.
    Updated Read Me

## [3.0.2] - 2026-09-18

### Improvements
    Introduces reusable Site management and a shared Site picker across pairing, manual config, and settings.
    Wi‑Fi, location, timezone, and city data are now sourced from Sites, with a browser geolocation helper and inline Site creation flow.
    This also updates scheduler payloads and safety checks
    Adds MIT licensing, and refreshes related UI text/layouts.

### Bug
    Correction for Scheduling Import

## [3.0.2test2] - 2026-09-16

### Improvements
    Rewrite RTSP handling to use FFmpeg subprocess (stable decoding, spawn/terminate, stall/respawn, JPEG extraction)
    Add check_ffmpeg_available + i18n message.
    Fix camera_stream disconnect race and add debug logs.
    Enhance schedule editor: parse exposures, auto-compute duration from count×exposure, update defaults (shutter, duration, stacked).
    Add new translation keys (en/fr) including device-occupied and ffmpeg-missing messages.
    Surface specific connection error when device is occupied.
    Minor UI/theme padding tweak
    Update CHANGELOG and a NiceGUI storage entry.
    Add Wifi Only Configuration Page to a Dwarf
    Add Sites Management Page

### Bug
   Remove OpenCV : big latency problem

## [3.0.2.test1] - 2026-09-14

### Improvements
   Add RTSP Viewer with OpenCV
   Add Manual Motor Positionning Section
   Add Specific Motor Action for Dwarf Mini
   Add Native Schedule Support
   Add Native Schedule Editor
   Add Routes
   /catalog: Serves the great DSO catalog page from JD Stefaniac to prepare your best options for your Astro Sessions
   Add Api Routes
       To Get Dwarfs Info and Post Schedule option to directly create session from catalog page
   Use already known value for Wifi SSID, Password , Location and Stellarium port

### Bug
   Add Specific Motor Action for Dwarf Mini : no Rotation Reset for Mini

## [3.0.1] - 2026-09-09

### Bug
   Install Static Images Procedure correction

## [3.0.0] - 2026-09-09

### Improvements
    Nice GUI new Interface
    Dwarflab API 3.0 support
    Adding Session Explorer
    Multi Devices Support at same time

## [1.7.6] - 2025-10-15

### Improvements
    Add Support for Dwarf Mini
    Add UI controls (Reboot, Toggle Lights, Stop Session)
    Improve scheduler JSON sorting to handle missing or malformed datetimes.
    Harden session flow and retries: add retry wait-end functions, make try_attemps interruption-aware, adjust exposure/IR handling for different devices

### Bug
    Due to new V3 API from Dwarflab, this version is not working anymore!

## [1.7.5] - 2025-09-19

### New Features
- **Auto Focus button**: Added dedicated Auto Focus button to the Main tab for quick access to autofocus functionality using the start_auto_focus function.
- **Session stop choice dialog**: When stopping the scheduler, users can now choose between stopping just the scheduler or stopping the current session and scheduler together.
- **Enhanced thread management**: Improved thread coordination with comprehensive monitoring of both stop_astro_photo and scheduler threads, including 150-second wait period after thread completion.

### Improvements
- **Camera-specific UI controls**: Dwarf 3 Wide Lens camera type now automatically disables IR Cut and Binning selection dropdowns and sets IR Cut to the first option for optimal device compatibility.
- **Responsive session stopping**: Sessions now properly respond to stop events through enhanced stop_event parameter passing to session execution functions.
- **Better scheduler control**: Stop scheduler button now properly returns to "Start Scheduler" state and becomes clickable after all threads have completed.

### Bug Fixes
- **Fixed scheduler button state**: Resolved issue where stop scheduler button remained unclickable after stopping, preventing users from restarting the scheduler.
- **Fixed thread cleanup**: Enhanced thread monitoring to ensure both photo stopping and scheduler threads complete before proceeding with shutdown operations.
- **Fixed dropdown state management**: Camera type changes now properly enable/disable related controls based on device capabilities.
- **Binning and IRCut values were INT**: Quoted values in string test for binning and ircut NOTICE output values.

## [1.7.4] - 2025-09-10

### New Features
- **Custom application icon**: Application window now displays the custom Astro Dwarf Scheduler icon instead of the default feather icon in the title bar.

### Improvements
- **Enhanced camera type change validation**: When camera type is changed in settings tab, exposure and gain values are now validated against actual dropdown lists and automatically set to valid values that exist in the dropdown options.
- **Smart default value selection**: Improved camera type change handler to use intelligent fallback logic - if preferred default values don't exist in dropdown lists, automatically selects the first available valid option.
- **Dynamic dropdown synchronization**: Camera type changes now properly update both the field values AND the dropdown option lists simultaneously for consistent user experience.

### Bug Fixes
- **Fixed invalid dropdown values**: Resolved issue where camera type changes could set exposure and gain to values that don't exist in the device-specific dropdown lists.
- **Fixed dropdown option updates**: Camera type changes now properly refresh the exposure and gain dropdown options to match the selected device type.

### Technical Improvements
- **Enhanced value validation**: Added comprehensive validation to ensure exposure and gain values always correspond to valid dropdown options for each device type.
- **Improved error handling**: Added graceful fallback for icon loading with proper exception handling to prevent application crashes if icon file is missing.

## [1.7.3] - 2025-09-07

### New Features
- **Config-specific settings management**: Each device configuration now maintains separate INI files (config.ini, config_Test.ini, etc.) with independent settings for each device type.
- **Enhanced exposure and gain controls**: Settings tab now uses device-specific dropdown menus matching Create Session tab restrictions, preventing invalid value selection.
- **Device-type aware restrictions**: Exposure and gain options automatically update based on selected device type (Dwarf II, Dwarf 3 Tele Lens, Dwarf 3 Wide Lens).

### Improvements
- **Optimized settings synchronization**: Create Session tab defaults now update only when relevant settings actually change, improving performance and user experience.
- **Enhanced IR Cut filter management**: Filter options dynamically update based on device type selection with proper value mapping.
- **Improved initialization order**: Fixed tab initialization sequence to ensure all tabs are properly populated on application startup.

### Bug Fixes
- **Fixed empty tabs on startup**: Resolved issue where Sessions Overview, Results Session, Create Session, and Edit Sessions tabs appeared empty until settings were modified.
- **Fixed settings tab dropdown population**: Exposure and gain dropdowns now properly populate with device-appropriate values on initial load.
- **Fixed config file pollution**: Prevented dropdown references from being saved to configuration files, maintaining clean INI file structure.

### Technical Improvements
- **Enhanced callback system**: Implemented targeted update mechanisms for cross-tab communication with proper change detection.
- **Improved dropdown value management**: Added automatic population of device-specific exposure/gain values with proper fallback handling.
- **Better error handling**: Enhanced tab initialization with robust error handling and graceful degradation.

## [1.7.2] - 2025-09-03

### Bug Fixes
- **Fixed GUI widget destruction errors**: Resolved "bad window path name" errors in session_info_label by adding robust widget existence checking and graceful error handling.
- **Fixed tab change event errors**: Resolved "expected integer but got" errors in tab navigation by improving tab index validation and type conversion handling.
- **Improved application stability**: Added comprehensive exception handling for Tkinter widget operations including AttributeError, TypeError, and IndexError in addition to TclError.

### Improvements
- **Enhanced widget lifecycle management**: GUI operations now fail gracefully without crashing the application when widgets are destroyed.

## [1.7.1] - 2025-08-31

### Bug Fixes
- **Fixed dwarf_id inconsistency between Bluetooth and IP connections**: Device returns actual ID (2=Dwarf II, 3=Dwarf III) while config stores offset ID (1=Dwarf II, 2=Dwarf III). IP connection now properly converts actual device ID to offset before storing, ensuring consistent behavior across all connection methods.
- **Fixed config corruption on Bluetooth connection failure**: IP and ID values are no longer set to None when Bluetooth connection fails. Added proper null checks and validation to prevent config file corruption.
- **Improved Bluetooth connection error handling**: Enhanced error handling in `connect_ble_dwarf_win` and `connect_ble_dwarf` functions to only update config with valid values and prevent None values from being stored.

### Documentation
- **Updated README.md**: Added technical documentation about dwarf_id handling and configuration issues in the Troubleshooting section.

## [1.7.0] - 2025-08-26

### Many changes and additions on evolution branch
- Edit Sessions tab added
- Improved form layout on tabs
- Added Video Preview on main tab
- Session management and color changes
- Session information improved
- Colors on log console
- Improved button functionality
- Fixed a few bugs
- Can import Telescopius Lists now
- Merged Start/Stop scheduler button
- Improved github runner workflow
- Possibly broke some things but are not aware of any yet

## [1.6.2] - 2025-03-25

### Integrate New Bluetooth API
- DirectBluetooth Cmd has more parameter: select first device found or by Name

## [1.6.1] - 2024-12-24

### Bugfix
- Correction for creating exe working for direct bluetooth connections

## [1.6.0] - 2024-12-21

### Add Direct Bluetooth connection
- Permits to choose direct or web based bluetooth connection

## [1.5.9] - 2024-11-25

### Bugfix
- Correction for Update Results Tab Page not working

## [1.5.8] - 2024-11-25

### Add multi Configuration mode
- Permits to use more than one device alternatively with keeping the data separate for D2 or D3
- Can launch multiple parallel sessions with multiple instances of the program for more than one device

###  EQ Mode functionnality validated

## [1.5.7] - 2024-11-07

### Add autom EQ Mode functionnality
- Neet to validate this new functionnality

## [1.5.6] - 2024-10-29

### Bugfix
- Check Dwarf type during STA connection if not using bluetooth

## [1.5.5] - 2024-10-25

### Add Results Analysing
- Add Results Page
- Add Multi Select in Overview Page

- Since version 1.5.4 : Telescopius List management
- Import Mosaic List or Object List from Telescopius
- Import Custom Mosaic List from Telescopius too
 
### Bugfix
- Add retry during Imaging Session
- Timers taking in account for calculating session duration

## [1.5.4] - 2024-10-24

### Add help in Settings Tab
- Add Autofocus option
- Add Timer for actions
- Add option to enter coordinnates in DD:MM:SS.s format
- Change settings page 

### Bugfix
- Correction on coordinnates values from Stellarium to J2000 values
- Correction for conversion for coordinnates
- Correction on Logs trace

## [1.5.3] - 2024-10-17

### Add help in Settings Tab
- Add Help Message
- Add Button to get location data from address

## [1.5.2] - 2024-10-16

### Bugfix
- Correction on Config : Avoid using same keys for config and session settings

### Add functions and control in Session Creation

- Add Goto Solar Systems Objects
- Add option to do only Imaging
- Add option to not do Goto

## [1.5.1] - 2024-10-11

### minor Bugfix

-- Bugfix

- allow session to be selected

## [1.5] - 2024-10-11

### Add control in Tasks Settings

-- Bugfix

- Avoid error if settings doesn't exist
- Control the settings in each section to ignore task if mandatory one doesn't exist

## [1.4] - 2024-10-10

### Wide-Angle for session creation

-- GUI Feature

- Add Wide-Angle selection for new sessions
- Display Wide-Angle configuration from session

-- Bugfix

- fixed typo

## [1.3] - 2024-10-10

### Added

-- Console Feature

- Add parameters --ip (ip_value) --id (2 or 3) and --ble (to start bluetooth at startup)
- the console can be used in a headless environnement until it can connect to wifi network (the connection can be set with Dwarfium)
-- GUI Features
- Add Logs in main window

## [1.2] - 2024-10-10

### Bugfixes

- Bugfixes
