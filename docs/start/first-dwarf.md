---
tags:
  - Lite
  - Hub
  - Scope Archive
  - Beginner
---

# Add your first Dwarf

## 1. Create a Site (Dwarfium Lite)

A **Site** is a place you observe from: a **Wi-Fi network** + a **location** (latitude, longitude, timezone). You type them once and pick the Site everywhere else — pairing, manual configuration, a Dwarf's settings.

1. Open Dwarfium Lite → **Sites** → **Add a site**.
2. Give it a name (`Home`, `Club field`…), the Wi-Fi name and password, and the location — **Use current location** fills it from the browser.

!!! note "Why the location matters"
    The Dwarf needs it for **EQ Solving** (polar alignment), and every time in the app is the **Site's time**, whatever the timezone of the PC or of the phone you use.

You can also create a Site on the spot with the **+** next to any Site picker.

## 2. Add the Dwarf (Dwarfium Lite)

=== "With Bluetooth (pairing)"

    1. On the dashboard, tap **+**.
    2. Pick the Site (for its Wi-Fi) and give the Dwarf a name.
    3. **Pair**: the app finds the Dwarf over Bluetooth (pick it if several answer) and makes it join the Site's Wi-Fi.

    Close the official DwarfLab app first: a Dwarf accepts one Bluetooth connection at a time.

=== "Without Bluetooth (manual configuration)"

    Use this when the Dwarf already joins your Wi-Fi on its own (set up once in the DwarfLab app), or when the PC's Bluetooth doesn't work.

    1. On the dashboard, click the **Wi-Fi icon** → *Manual device config (no Bluetooth)*.
    2. Pick the Site and the model, type the **Device IP** (shown in the DwarfLab app, *My Device*).
    3. **Read from the Dwarf** fills in its UID: the IP is enough when the Dwarf is on the network.

The Dwarf now has its card on the dashboard: connection, battery, temperature, free space, current capture. **Connect all** connects every Dwarf in one click.

## 3. Declare it in Scope Archive (optional)

If you use Scope Archive, the Dwarf must exist there too — with its **USB path** (e.g. `I:\Astronomy`, DWARF 3 / mini) and/or its **IP** for FTP.

The quickest way is the **Hub → Dwarfs** tab: it shows the Dwarfs of both apps side by side and offers, for a Dwarf only in Lite, **create it in Scope Archive, already linked**. Once linked, the buttons that jump from one app to the other work for it.

!!! tip "Which Dwarf is which?"
    Several Dwarfs on the table: the ✳ button of a row in the Hub's Dwarfs tab flashes that Dwarf's ring light. The **ID** printed on the Dwarf (last 6 characters of its MAC address) also ends its Bluetooth name, e.g. `DWARF3_A1B2C3`.

Doing it by hand instead: in Scope Archive, **Dwarf Configuration** → add the Dwarf; in Lite, the Dwarf's **Settings** → *Dwarfium Scope Archive URL* (`http://localhost:8080`) and *Dwarf Id* (its id in Scope Archive).

**Next:** [Your first night, end to end](first-night.md)
