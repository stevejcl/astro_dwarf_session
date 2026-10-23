---
tags:
  - Lite
  - Hub
  - Connection
---

# Connect and manage Dwarfs

## Add a Dwarf { #add-a-dwarf }

**App:** Dwarfium Lite — see the full walkthrough in [Add your first Dwarf](../start/first-dwarf.md).

- **Bluetooth pairing:** dashboard → **+** → pick a Site → **Pair**.
- **No Bluetooth:** dashboard → **Wi-Fi icon** → pick a Site and the model → type the **Device IP** → **Read from the Dwarf** → save.

## Use the same Wi-Fi and location everywhere (Sites) { #sites }

**App:** Dwarfium Lite → **Sites**

A Site = a Wi-Fi network + a location + a timezone. Create one per place you observe from, then:

- pairing and manual configuration take the Site's Wi-Fi;
- a Dwarf's **Settings** → **Apply from site** fills its location and Wi-Fi;
- every time shown and typed for that Dwarf is in its Site's timezone (handy for a remote site in another timezone).

## Wake up a Dwarf that no longer answers { #wake-up }

**App:** Dwarfium Lite

When a Dwarf no longer answers on the home Wi-Fi (even to the official app), switching it to its own hotspot over Bluetooth wakes it up; it then joins the home Wi-Fi again.

- **PC close to the Dwarf:** the Dwarf's **Settings** → **Force Bluetooth reconnect**.
- **PC too far:** open `/wake-dwarf` on your phone, next to the Dwarf. The QR code and the link are in the Dwarf's **Settings** → *Wake up from the phone (hotspot)*. Tap **Wake up (hotspot)**, then if needed **Back to the home Wi-Fi**.

!!! warning "Phone browser"
    The page uses the phone's Web Bluetooth.
    **Android / Chrome:** open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`, enable it, add the app's address (e.g. `http://192.168.1.10:8090`) and relaunch Chrome — once per phone.
    **iPhone:** Safari has no Web Bluetooth, use the **Bluefy** browser.
    Close the official app first (one Bluetooth connection at a time).

## Fix a Dwarf whose IP changed { #ip-changed }

**App:** Dwarfium Lite → the Dwarf's **Settings**

- You know the new IP: **Manually update IP** → **Save new IP**.
- You don't: **Force Bluetooth reconnect** (PC near the Dwarf) reads it and saves it.

If you use Scope Archive, the IP must be updated there too: the **Hub → Dwarfs** tab shows the difference and copies it across.

## Know which Dwarf is which { #identify }

**App:** Dwarfium Hub → **Dwarfs**

The ✳ button of a row flashes that Dwarf's ring light (through Dwarfium Lite, never during a capture). The **ID** — last 6 characters of the MAC address printed on the Dwarf — also ends its Bluetooth name (`DWARF3_A1B2C3`).

## Hide or reorder Dwarfs on the dashboard { #dashboard }

**App:** Dwarfium Lite → dashboard

Each card can be moved and hidden. A hidden Dwarf keeps only its header and isn't connected automatically — useful for a Dwarf you don't use for now.

!!! info "One app per Dwarf"
    Only one Dwarfium Lite on a PC drives a given Dwarf at a time. Another instance shows it as *used elsewhere*, with a link to the first one's watch page.

## Link a Dwarf between Lite and Scope Archive { #link }

**App:** Dwarfium Hub → **Dwarfs**

The tab lists the Dwarfs of both apps side by side and says what to do:

| On screen | What to do |
|---|---|
| **Same Dwarf (verified)** / **Same Dwarf?** | Link it (or link all the suggestions) |
| **Not in Scope Archive** | Create it there, already linked |
| **Not in Dwarfium Lite** | Opens Lite's manual configuration filled in — only the Site is left to choose |
| **Linked** | Copy the name, IP or ID across when they differ |
| **Not the same Dwarf!** / **Broken link** | Unlink, or link to the right one |

Lite's side is only changed while Lite is stopped (the Hub asks).
