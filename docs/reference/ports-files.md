# Ports, pages and files

## Ports

| App | Default port | Notes |
|---|---|---|
| Dwarfium Scope Archive | **8080** | Local only, unless started with `--lan` / Hub *LAN access* |
| Dwarfium Lite | **8090** with the Hub | Started by hand: chosen automatically and printed at startup; `--port` fixes it. Always reachable on the network |
| Dwarf live view | 8092 | `http://<dwarf-ip>:8092/mainstream` (Tele), `/secondstream` (Wide) |

## Dwarfium Lite pages

| Address | Page |
|---|---|
| `/` | Dashboard |
| `/session/<dwarf>` | A Dwarf's page (`/programs`, `/explorer`, `/settings` below it) |
| `/sites`, `/pairing`, `/manual-config` | Sites, Bluetooth pairing, manual configuration |
| `/plan-target` | Plan a target (opened by Scope Archive) |
| `/catalog` | DSO catalog, sky map, mosaic planner |
| `/mosaic-planner-en`, `/mosaic-planner-fr` | Milky Way mosaic planner |
| `/watch`, `/watch/<dwarf>` | Watch mode (read-only) |
| `/wake-dwarf` | Wake up a Dwarf from the phone |
| `/logs` | Live log |

## Where the data lives

=== "Dwarfium Lite"

    | File / folder | Holds |
    |---|---|
    | `devices.json`, `config_*.py` / `config_*.ini` | Your Dwarfs |
    | `Devices_Sessions/<dwarf>/Astro_Sessions/{ToDo,Current,Done,Error}/` | Programs |
    | `end_of_night.json` | After the session / end of the night settings |
    | `task_check_cache.json` | View / Check results |
    | `catalog_add_on.json` | Targets added from the catalog page |
    | `components/locales/` | Languages |

=== "Scope Archive"

    | File / folder | Holds |
    |---|---|
    | `dwarf_backup.db` (+ `.bak`, `.last`) | The archive database and its automatic copies |
    | `db/dso_catalog.json` | DSO catalog (also used by Lite when installed side by side) |
    | `transfer_journal.json` | Transfer history |
    | `logs/` | Analyze-everything logs |
    | On the backup drive: `MOSAIC_WCS`, `FIXED_FOREGROUND` | Milky Way mosaics, fixed foregrounds |

=== "Hub"

    | File / folder | Holds |
    |---|---|
    | `hub_config.json` | Hub settings, instances |
    | `<app>/.hub_version.json`, `<app>/.hub_backup/` | Installed version, previous version's files |
    | `sync_backups/` | Zips made before a synchronization |
