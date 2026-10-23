# Troubleshooting

??? question "A Dwarf shows *Disconnected* but its light is solid"
    Give it a few seconds: Lite validates the connection with a real round-trip, since a socket can look open while the Dwarf stopped answering. Still nothing → [wake it up](../how-to/connect.md#wake-up) or [check its IP](../how-to/connect.md#ip-changed).

??? question "The Dwarf no longer answers on the home Wi-Fi, even to the official app"
    Switch it to its hotspot over Bluetooth: **Force Bluetooth reconnect** from the PC, or `/wake-dwarf` from a phone next to it. → [Wake up](../how-to/connect.md#wake-up)

??? question "Bluetooth pairing finds no adapter"
    A common issue on some PCs. Use the [manual configuration](../start/first-dwarf.md#2-add-the-dwarf-dwarfium-lite): the IP is enough.

??? question "No live view"
    The live view needs **FFmpeg** (said on the Dwarf's page and in the log when missing), and the Dwarf's port 8092 reachable: `http://<dwarf-ip>:8092/mainstream`.

??? question "*Archive in Dwarfium Scope Archive* is greyed"
    Scope Archive isn't running, or Lite doesn't know its URL: set *Dwarfium Scope Archive URL* and *Dwarf Id* in the Dwarf's Settings (or link it in the [Hub](../how-to/connect.md#link)). Scope Archive must be V3.4.0+.

??? question "A program is in Error but the Dwarf kept capturing"
    Programs → Results → **Force resume**. → [Force resume](../how-to/capture.md#force-resume)

??? question "The Dwarf didn't power off at the end of the night"
    Something was still planned (a program in ToDo, a native schedule task, a schedule waiting to be sent), *Bulky accessory mounted* is ticked, or Lite was restarted during the delay. → [Unattended](../how-to/night.md)

??? question "The Dwarf is shown in red in the Hub's Installations tab"
    It is connected to two Dwarfium Lite installations: disconnect it from one.

??? question "Network path not found with a computer's name, while its IP works (Windows)"
    Windows resolved the name to another address (often a local IPv6 one). Use the full Tailscale name (`\\pc-name.tailXXXX.ts.net\share`) or the IP (`\\100.x.y.z\share`). `Test-NetConnection <ip> -Port 445` (sharing) and `-Port 8090` (Lite) tell what is reachable.

??? question "Windows messages *ConnectionResetError [WinError 10054]*"
    Harmless Windows / asyncio noise.

??? question "Scope Archive warns the Dwarf type doesn't match"
    It checks the stacked JPEG sizes before scanning. Fix the model in **Dwarf Configuration**. (DWARF 3 and mini can't be told apart over FTP: the configured model is trusted.)

Still stuck? Open an issue with a log excerpt (Lite: `/logs`):
[Dwarfium Lite](https://github.com/stevejcl/astro_dwarf_session/issues) ·
[Scope Archive](https://github.com/stevejcl/dwarfium-scope-archive/issues) ·
[Hub](https://github.com/stevejcl/dwarfium-hub/issues)
