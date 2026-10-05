# Changelog

## [Unreleased]
  ### BugFix
    ### No more "slot busy" flood during a program
    While a program (or a run resumed after a restart) holds the device, the connection health check is skipped
    instead of being denied and logged on every poll tick of every open page (a resumed run logged it every second
    all night); a check denied by a one-off command waits for the normal interval before retrying.
    ### Target of a program run by this app
    The dashboard card and the watch page showed no target for a program run by this app (started or resumed): its
    goto target was read from the wrong part of the program. Fixed, with the target name the Dwarf sends as a
    fallback for a program without goto.
    ### Program followed again after a restart
    A program left in Current/ by an app restart during its capture was only resumed if its last step (the capture
    start - nothing is recorded while it captures) was less than 5 min old: a restart at 01:00 for a capture started
    at 22:39 left it unfollowed. It is now resumed when the Dwarf reports capturing the program's target, or, while
    that name isn't known yet, when the last step is less than 15 h old - never when the Dwarf reports another
    target. Retried as soon as the Dwarf's first progress notification brings the target name. The program's end
    time is applied again while resumed (counted from the program's start date/time, across midnight).
    ### "Use best slot" (program editor)
    A best slot whose start has already passed now starts 5 min from now (site time), also in the native schedule
    editor and for a click on the curve; a slot already over is refused with a message.
    The image count is set to fill the slot (time between the start and the end time / exposure, per view for a
    mosaic): it stayed at its default (20), so the program stopped long before the chosen end time.
  ### Improvements
    ### Preview: stacked image / last frame
    The device page's camera previews get a "Stacked / Last frame" switch, the official app's own toggle
    (displaySource parameter, CMD_PARAM_SET_GENERAL_INT_PARAM - 1 stacked, 0 last frame, from a capture of the
    official app). Usable during a program's capture, which sends no command of its own while it waits.
    ### Force the resume of a program in error
    Programs page, Results: a failed run shows its error date, and a "Force resume" button when the Dwarf is still
    capturing that program's target and the error is less than 15 h old (e.g. a run ended in error after 3 failed
    attempts while the Dwarf went on shooting). It moves the file back to Current/ (pending, last step now; dwarf,
    shots and processed date removed) and runs the normal resume, end time included.
    ### Hide a Dwarf on the dashboard
    The eye button on a card hides a Dwarf not used for now: only its header (name, IP, status) stays, it moves after
    the others, and it isn't auto-connected (no more failed attempts for a Dwarf that is off). The same button shows
    it again. Saved in device_prefs.json in the working folder.
    ### Dashboard order
    The ⇅ button on a card moves it first, up, down or last (hidden Dwarfs stay after the others, ordered among
    themselves the same way). Saved in device_prefs.json, also used by the watch dashboard.
    The watch dashboard (/watch) shows the same order and hidden Dwarfs (display only, no hide button).
    ### Current target on the dashboard and the watch page
    The dashboard card and the watch page (/watch/<device>) now show the target being shot: the goto target of
    the program run by this app (also added to the program name in the "program in progress" banner), or the
    native shooting schedule task run by the Dwarf itself ("Schedule <name> · <target>", task n/total and its
    time window, in the device's timezone), also before its capture starts (goto, calibration).
    The schedule list is read from the Dwarf only when a capture starts outside a program of this app, once a
    little after each task's start (so a task the Dwarf didn't run isn't shown for its whole window), and every
    10 min while a capture stays unexplained - never polled otherwise.
    Any other capture (started from another app, by hand...) shows the target name the Dwarf itself sends in its
    tracking / capture progress notifications. Requires dwarf_python_api 3.1.5.
    ### One instance per Dwarf on this PC
    Two Astro Dwarf Session open together (e.g. the .exe and a source run) connected to the same Dwarf with the
    same client_id: the Dwarf dropped one each time the other connected, and both reconnected in turn. The first
    instance to connect now holds the Dwarf (lock file in the temp folder, released on Disconnect, on exit or after
    a crash); the other one doesn't connect, its card says the Dwarf is used by another instance with an "Open its
    view" link to that instance's watch page (target, program, progress), and it connects by itself once the Dwarf
    is free. Only instances with this change take part: an older version still running isn't detected.
    A Dwarf that drops the connection right after each reconnection (3 times within a minute of connecting) is
    being used by another client - a Dwarf Mini accepts only one connection whatever the client_id (an older
    version, another PC, the official app): auto-reconnect then stops instead of taking it back in a loop, and the
    card says so until the user connects again.

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
