# Aqua Tracka: the Wi-Fi dashboard (ESP32-C3)

Two programs, two boards:

| Board | Program | What it does |
|---|---|---|
| **Arduino Nano** | `../WaterValveController.ino` | Runs the water controller: counts the water, works the valve, button, remote and lights. Sends its readings on D11 and takes commands on D12. |
| **ESP32-C3** (Waveshare ESP32-C3-Zero) | `firmware/aqua_tracka-flash-at-0x0.bin` (source: `aqua_tracka/`) | Makes the Wi-Fi network **VAT_Aqua_Tracka** and shows the dashboard at **http://192.168.4.1**. Every button on the page is passed to the Nano, which does the work. |

The controller works on its own without the ESP32. The dashboard adds:

- **Home:** a live water gauge (count towards the limit), flow rate, session total, time until the
  limit at the current flow, a 5-minute flow graph, and buttons to choose the limit and reset the count.
- **Calibrate:** a step-by-step calibration with any bucket (type in the litres it held), or type
  in the pulses per litre.
- **Settings:** the three limits, the warning pulses (how many, how long), keep flowing or **stay
  shut** after the limit, the confirm clicks, hold times, calibration bucket, remember-the-limit,
  and the hardware options. **Reset to defaults** and **Factory reset**.
- **Diagnostics:** every raw reading (pulses, frequency, state, valve), the button and remote
  inputs lighting up live, a valve test, the link between the boards, and an event log.
- **Help:** how to use the system, on the phone.

Settings changed on the page are saved in the Nano (EEPROM), so they stay after a power cut, also
without the ESP32. The page is built for phones and works in light and dark mode. It needs no
internet: everything is inside the ESP32.

**Try the page without any hardware:** open `aqua_tracka/web/preview.html` in a browser. It runs a
pretend controller with water flowing.

Test in this order: each step checks one thing, so a problem shows up where it starts.

## 1. The Nano

The Nano needs the web-ready sketch (firmware 2): the one in this folder's parent,
`WaterValveController.ino`. Open it in the Arduino IDE, choose **Arduino Nano** (if the upload
fails, **Tools → Processor → ATmega328P (Old Bootloader)**) and upload. It works exactly as before;
the settings at the top of the sketch are now the defaults that the page's **Reset to defaults**
brings back.

**Check it:** the **Serial Monitor at 115200 baud** shows a status line every second and, at
power-up, `Web: join Wi-Fi VAT_Aqua_Tracka, open http://192.168.4.1`.

## 2. The ESP32-C3 on its own

**Flash it**, either way:

- **In Chrome or Edge, no installing:** go to https://espressif.github.io/esptool-js/. Set **Baudrate**
  to `115200`, press **Connect** and pick the C3's port. If no port appears, hold the **BOOT** button
  while plugging the C3 in. Press **Erase Flash** and wait for it to finish. Then set **Flash Address**
  to `0x0`, choose `firmware/aqua_tracka-flash-at-0x0.bin`, and press **Program**. When it finishes,
  press the C3's **RESET** button (or unplug it and plug it back in).
- **Arduino IDE** (with Espressif's *esp32* boards package, version 3.x, installed): open
  `aqua_tracka/aqua_tracka.ino`. Choose board **ESP32C3 Dev Module**, set **USB CDC On Boot:
  Enabled** and **Partition Scheme: Huge APP (3MB No OTA/1MB SPIFFS)**, then upload. No libraries to
  install: everything it uses comes with the boards package.

**Check it** (no Nano needed yet):

- [ ] The **Serial Monitor at 115200** on the C3's USB shows, every 2 seconds:
      `Wi-Fi VAT_Aqua_Tracka, page http://192.168.4.1, 0 phone(s) | Nano link: NO DATA ...` (no data yet is right).
- [ ] On a phone, join the Wi-Fi network **VAT_Aqua_Tracka** (there's no password). Many phones then
      show "sign in to network": tap it and the dashboard opens. Otherwise **turn off mobile data**,
      choose to **stay connected** if it warns "no internet", and open **http://192.168.4.1** (type
      all of it, with `http://`).
- [ ] The dashboard appears with **Controller offline** at the top and "Waiting for the controller".

## 3. Join them

Unplug both boards first. On the controller PCB, the ESP32-C3 plugs into **J4** (5V, GND, RX, TX):
the dividers are on the board. Hand-wired:

```
Nano D11 ── 1 kΩ ──┬── ESP32-C3 GPIO20 (RX)
                   └── 2 kΩ ── GND
ESP32-C3 GPIO21 (TX) ── 1 kΩ ── Nano D12
Nano GND ──────────────────── ESP32-C3 GND
5 V supply ─────────────────── ESP32-C3 5V
```

**Never** connect Nano D11 straight to the C3: the Nano's 5 V damages the C3. The C3's 3.3 V on
D12 is fine for the Nano.

- [ ] The C3's Serial Monitor now says `Nano link: OK`, with the count of lines going up and the
      Nano's latest reading.
- [ ] The dashboard shows **Live** at the top, the water count and the flow. Run some water.
- [ ] Tap a limit on the Home tab: within a second or two the Nano's light changes and the page
      says "✓ ... chosen".
- [ ] **Diagnostics:** press the push button and each remote button: the matching square lights up.
      **Test valve** clicks the valve twice.

## If something doesn't work

| What you see | What to check |
|---|---|
| Web flasher: no port | Hold **BOOT** while plugging the C3 in, then **Connect**. Use a data USB cable, not a charge-only one. |
| Web flasher: "Failed to leave compressed flash mode" (status 196) | Writing to the C3's flash failed. Unplug the C3, hold **BOOT** while plugging it back in, press **Connect** at 115200, **Erase Flash**, then **Program** again. Use a short data cable straight into the computer (no hub). |
| No Wi-Fi network | The C3's Serial Monitor: "Wi-Fi FAILED" means press RESET; nothing at all means flash it again (Erase Flash first). |
| The network disappears a few metres away | The transmit power is set low (8.5 dBm) because some C3 boards are unstable at full power. Raise `WIFI_POWER` in `aqua_tracka.ino` and build it again. |
| The page won't open | Stay joined to VAT_Aqua_Tracka, mobile data off, and type `http://192.168.4.1` exactly. |
| Page says **Dashboard offline** | The phone has left the network (phones do this when it has no internet). Rejoin and reload. |
| Page says **Controller offline**; C3 says "NO DATA" | Nothing on GPIO20: the D11 → divider → GPIO20 wire and the shared GND. Is the Nano powered and running? |
| C3 says "bytes arrive but no good lines" | The Nano needs the web-ready sketch (step 1); check the divider resistors (1 kΩ to D11, 2 kΩ to GND). |
| Readings show, but the page's buttons say "no answer from the controller" | The return wire: GPIO21 → 1 kΩ → Nano D12. Diagnostics → Link → "Commands failed" counts them. |
| Buttons say "not known by the controller" | The Nano has the old sketch: upload `WaterValveController.ino` again. |

## How it works

The Nano sends two kinds of line to the ESP at 9600 baud, one JSON object each:

- **status**, every second and straight after a command:
  `{"t":"s","n":3394,"c":58,"s":3394,"hz":1080,"m":1,"st":0,"v":1,"cp":0,"in":0,"ppl":6480,"cal":0,"ack":12,"ok":1,"ev":2,"ec":2,"es":3,"ex":50,"g":0,"bad":0,"up":1142}`
  — total pulses `n`, pulses counted towards the limit `c`, session pulses `s`, sensor frequency ×100
  `hz`, limit `m` (0–2, 3 = free flow), state `st` (0 normal, 1 limit warning, 2 confirm clicks,
  3 calibrating, 4 valve held shut), valve open `v`, calibration pulses `cp`, inputs `in` (bit 0 push
  button, bits 1–4 remote A–D), pulses per litre ×100 `ppl`, calibrated `cal`, the last command's
  number and result `ack`/`ok`, the latest event `ev`/`ec`/`es`/`ex`, noise pulses ignored `g`,
  damaged commands `bad`, seconds since power-up `up`.
- **settings**, every 10 seconds and after a change:
  `{"t":"cfg","l1":25,"l2":50,"l3":100,"ap":4,"am":500,"ah":0,"cc":2,"cm":250,"rs":0,"rl":1,"rh":2000,"ch":20,"bk":70,"vn":0,"va":0,"ra":0,"ppl":6480,"cal":0,"fw":2}`

The ESP sends commands as `$<number>,<command>*<checksum>` (XOR of the characters between `$` and
`*`), only in the quiet moment straight after a Nano line, because the Nano's software serial port
can't send and receive at the same time. It repeats a command that gets no answer after 2.5 s (up
to 4 times); the Nano runs each number once. The commands are listed in the Nano sketch above
`runCommand()`.

The ESP serves the page (gzipped, about 32 KB) and two addresses: `GET /api/status` (everything
above plus the link counters, the event log and the flow history) and `POST /api/cmd` with
`c=<command>`.

## Changing the page

Edit `aqua_tracka/web/index.html` (and `web/demo.js` for the preview), then run
`python3 aqua_tracka/tools/make_page.py`: it packs the page and the logo into `web_page.h` and
rebuilds `web/preview.html`. Pushing to GitHub builds the flashable `.bin` again (see
`.github/workflows/aqua-tracka-firmware.yml`): it appears in `firmware/` a few minutes later.
