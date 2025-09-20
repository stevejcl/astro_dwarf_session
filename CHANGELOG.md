# Changelog

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
