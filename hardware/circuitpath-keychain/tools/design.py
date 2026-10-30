"""CircuitPath Keychain: the single source of truth for parts, nets and placement.

Both build_sch.py (schematic) and build_pcb.py (board) read this file, so the two
can never disagree about what connects to what.  Edit here, then re-run build.sh.

Coordinates are millimetres, +x to the right, +y DOWN (KiCad's PCB convention),
origin at the tip of the USB-A plug, y = 0 on the board's centre line.
"""

# ----------------------------------------------------------------- board shape
TAB_W = 12.0          # USB-A plug width (standard: 12.0 mm)
TAB_L = 12.0          # plug length from the tip to the body
BODY_H = 24.0         # body height
BODY_END = 118.0      # right-hand end of the board
CORNER_R = 6.0        # body corner radius (left side, beside the plug)
END_R = 8.0           # body corner radius (right end)
TIP_R = 1.2           # small rounding on the plug tip corners
BOARD_THICKNESS = 2.0 # USB-A plugs want ~2.0 mm; JLCPCB's maximum standard thickness

# Set True if a test with a real USB-A socket shows the fingers are mirrored.
USB_A_MIRROR = False

KEYRING_HOLE = (111.0, 0.0, 4.2)   # x, y, drill diameter

# ------------------------------------------------------------ LED matrix (7 x 11)
COLS, ROWS = 11, 7
MATRIX_X0, MATRIX_Y0 = 59.0, -6.0
COL_PITCH, ROW_PITCH = 3.0, 2.0
SPLIT = 6            # columns 1..6 are driven by U2, columns 7..11 by U3

MCU_XY = (47.5, 0.0)

# Free zone between the LED array and the keyring hole: logo box + two vertical 3 mm text lines
LOGO_BOX = (91.8, -4.25, 100.3, 4.25)      # x0, y0, x1, y1 (silkscreen outline; drop the real logo in here)
LOGO_TEXT = [("BNTS", 103.4), ("CircuitPath", 107.0)]   # (text, x), 3 mm tall, read bottom-to-top

FP_LIB = "/usr/share/kicad/footprints"

# ------------------------------------------------------------------- the parts
# Each part: ref, sym ("Lib:Name"), value, fp ("Lib:Name"), lcsc, pins {pin: net}, x, y, rot, side
# lcsc_ok: True = checked against a live LCSC / JLCPCB page; False = from memory, CHECK.
PARTS = []


def part(ref, sym, value, fp, lcsc, pins, x, y, rot=0, side="F", ok=False, mpn="", desc="", dnp=False, sch=None):
    PARTS.append(dict(ref=ref, sym=sym, value=value, fp=fp, lcsc=lcsc, pins=pins,
                      x=x, y=y, rot=rot, side=side, ok=ok, mpn=mpn, desc=desc, dnp=dnp, sch=sch))


def two(ref, kind, value, fp, lcsc, n1, n2, x, y, rot=0, side="F", ok=False, mpn="", desc=""):
    part(ref, "Device:" + kind, value, fp, lcsc, {"1": n1, "2": n2}, x, y, rot, side, ok, mpn, desc)


R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
mx, my = MCU_XY

# ---- USB-A plug (PCB fingers; custom footprint made by build_pcb.py)
part("J1", "Connector_Generic:Conn_01x04", "USB-A plug (PCB fingers)", "CircuitPath:USB_A_PCB_Plug", "",
     {"1": "VBUS_A", "2": "USB_DM", "3": "USB_DP", "4": "GND"}, 0, 0, desc="Edge fingers on the board tongue, no part to buy")

# ---- USB-C receptacle, vertical (opening faces up, matches the 'pill' in the sketch)
usbc = {"A1": "GND", "B12": "GND", "A12": "GND", "B1": "GND", "A4": "VBUS_C", "B9": "VBUS_C", "A9": "VBUS_C", "B4": "VBUS_C",
        "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM",
        "A8": None, "B8": None, "S1": "GND"}
part("J2", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C (vertical)", "Connector_USB:USB_C_Receptacle_G-Switch_GT-USB-7051x",
     "C2843970", usbc, 17.0, 0.0, rot=90, ok=True, mpn="GT-USB-7051A", desc="USB-C 16P vertical SMT, G-Switch")
two("R1", "R", "5.1k", R0603, "C23186", "CC1", "GND", 20.6, -10.6, ok=False, mpn="0603WAF5101T5E", desc="USB-C CC1 pull-down")
two("R2", "R", "5.1k", R0603, "C23186", "CC2", "GND", 20.6, 10.6, ok=False, mpn="0603WAF5101T5E", desc="USB-C CC2 pull-down")

# ---- power OR-ing: whichever USB port has power feeds the +5V rail
for ref, net, y in (("D1", "VBUS_A", -9.2), ("D2", "VBUS_C", 9.2)):
    part(ref, "Device:D_Schottky", "1N5819WS", "Diode_SMD:D_SOD-323", "C191023", {"1": "+5V", "2": net},
         14.2, y, ok=True, mpn="1N5819WS", desc="Schottky OR-ing diode")

# ---- USB data protection and series resistors
part("U4", "Power_Protection:USBLC6-2P6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "C7519",
     {"1": "USB_DM", "2": "GND", "3": "USB_DP", "4": "USB_DP", "5": "+5V", "6": "USB_DM"},
     mx - 7.0, -9.6, ok=True, mpn="USBLC6-2SC6", desc="USB ESD protection")
two("R3", "R", "22", R0603, "C23345", "USB_DM", "MCU_DM", mx - 7.6, -3.0, side="B", ok=True, mpn="0603WAF220JT5E", desc="USB D- series resistor")
two("R4", "R", "22", R0603, "C23345", "USB_DP", "MCU_DP", mx - 7.6, -1.0, side="B", ok=True, mpn="0603WAF220JT5E", desc="USB D+ series resistor")

# ---- the microcontroller
mcu = {"1": None, "2": "+5V", "3": "MCU_DM", "4": "MCU_DP", "5": "GND", "6": "UCAP", "7": "+5V", "8": "MAX_LOAD",
       "9": "MAX_CLK", "10": "MAX_DIN", "11": "ISP_MISO", "12": "LED_G_DRV", "13": "RESET", "14": "+5V", "15": "GND",
       "16": "XTAL2", "17": "XTAL1", "18": "BTN_A", "19": "BTN_B", "20": None, "21": None, "22": None, "23": "GND",
       "24": "+5V", "25": None, "26": None, "27": None, "28": None, "29": "BUZZ_A", "30": "BUZZ_B", "31": "LED_R_DRV",
       "32": "LED_Y_DRV", "33": "HWB", "34": "+5V", "35": "GND", "36": None, "37": None, "38": None, "39": None,
       "40": None, "41": None, "42": "AREF", "43": "GND", "44": "+5V"}
part("U1", "MCU_Microchip_ATmega:ATmega32U4-A", "ATmega32U4-AU", "Package_QFP:TQFP-44_10x10mm_P0.8mm", "C44854", mcu,
     mx, my, ok=True, mpn="ATMEGA32U4-AU", desc="USB microcontroller, Arduino Leonardo/Micro compatible")
part("Y1", "Device:Crystal_GND24", "16MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "C13738",
     {"1": "XTAL1", "2": "GND", "3": "XTAL2", "4": "GND"}, mx, 9.8, side="B", ok=True, mpn="X322516MLB4SI", desc="16 MHz crystal 3225")
two("C1", "C", "15p", C0603, "C1644", "XTAL1", "GND", mx - 3.6, 10.4, side="B", ok=True, mpn="CL10C150JB8NNNC", desc="Crystal load cap (check crystal CL)")
two("C2", "C", "15p", C0603, "C1644", "XTAL2", "GND", mx + 3.6, 8.2, side="B", ok=True, mpn="CL10C150JB8NNNC", desc="Crystal load cap (check crystal CL)")
two("C3", "C", "1u", C0603, "C15849", "UCAP", "GND", mx - 7.6, 1.2, side="B", ok=False, mpn="CL10A105KB8NNNC", desc="USB regulator capacitor")
two("C4", "C", "100n", C0603, "C14663", "+5V", "GND", mx - 7.6, 3.4, side="B", ok=False, mpn="CL10B104KB8NNNC", desc="Decoupling UVCC/VBUS")
two("C5", "C", "100n", C0603, "C14663", "+5V", "GND", mx + 5.0, -8.4, side="B", ok=False, mpn="CL10B104KB8NNNC", desc="Decoupling VCC")
two("C6", "C", "100n", C0603, "C14663", "+5V", "GND", mx - 6.2, -8.4, side="B", ok=False, mpn="CL10B104KB8NNNC", desc="Decoupling AVCC")
two("C7", "C", "100n", C0603, "C14663", "AREF", "GND", mx - 3.0, -8.4, side="B", ok=False, mpn="CL10B104KB8NNNC", desc="AREF filter")
two("C8", "C", "10u", C0805, "C15850", "+5V", "GND", mx + 1.0, -8.9, side="B", ok=False, mpn="CL21A106KAYNNNE", desc="Bulk capacitor")
two("R5", "R", "10k", R0603, "C25804", "+5V", "RESET", mx - 4.0, 8.6, side="B", ok=False, mpn="0603WAF1002T5E", desc="RESET pull-up")
two("R6", "R", "10k", R0603, "C25804", "HWB", "GND", mx + 7.2, -3.6, side="B", ok=False, mpn="0603WAF1002T5E", desc="HWB pull-down")

# ---- programming pads (bootloader / ISP), Tag-Connect TC2030-IDC-NL footprint = just pads, nothing to buy
part("J3", "Connector_Generic:Conn_02x03_Odd_Even", "ISP pads", "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical", "",
     {"1": "ISP_MISO", "2": "+5V", "3": "MAX_CLK", "4": "MAX_DIN", "5": "RESET", "6": "GND"}, mx + 8.5, 0.0, side="B",
     desc="Bare pads for the one-off bootloader burn (Tag-Connect TC2030-IDC-NL or pogo pins)")

# ---- 3 x 5mm indicator LEDs (through-hole) and their resistors
for ref_l, ref_r, name, net, y in (("D3", "R7", "RED", "LED_R", -6.6), ("D4", "R8", "AMBER", "LED_Y", 0.0), ("D5", "R9", "GREEN", "LED_G", 6.6)):
    part(ref_l, "Device:LED", name + " 5mm", "LED_THT:LED_D5.0mm", "", {"1": "GND", "2": net + "_A"}, 23.73, y,
         desc="5 mm through-hole LED, " + name.lower() + " (hand-solder or JLCPCB THT service)")
    two(ref_r, "R", "330", R0603, "C23138", net + "_DRV", net + "_A", 29.9, y, ok=True, mpn="0603WAF3300T5E", desc="LED resistor")

# ---- piezo buzzer: no driver parts, wired straight to two pins (D9 and D10) so it can be driven single-ended or bridged (louder)
part("BZ1", "Device:Buzzer", "Piezo 9x9", "Buzzer_Beeper:Buzzer_Murata_PKMCS0909E", "C910763", {"1": "BUZZ_A", "2": "BUZZ_B"},
     98.0, 0.0, side="B", ok=True, mpn="PKMCS0909E4000-R1", desc="9x9x1 mm SMD piezo sounder (passive: play it with tone())")

# ---- two user buttons
for ref, net, y in (("SW1", "BTN_A", -4.4), ("SW2", "BTN_B", 4.4)):
    part(ref, "Switch:SW_Push", "Button", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "C318884", {"1": net, "2": "GND"},
         36.0, y, ok=True, mpn="TS-1187A-B-A-B", desc="SMD tactile button 5.1x5.1")

# ---- LED matrix drivers (bottom side, under the LEDs)
for ref, chip_x, first, last, din, dout, tag in (("U2", MATRIX_X0 + COL_PITCH * 2.5, 0, SPLIT, "MAX_DIN", "MAX_CHAIN", "A"),
                                                  ("U3", MATRIX_X0 + COL_PITCH * 8.0, SPLIT, COLS, "MAX_CHAIN", None, "B")):
    pins = {"1": din, "12": "MAX_LOAD", "13": "MAX_CLK", "24": dout, "4": "GND", "9": "GND", "19": "+5V", "18": "ISET_" + tag,
            "22": None}
    digs = {0: "2", 1: "11", 2: "6", 3: "7", 4: "3", 5: "10", 6: "5", 7: "8"}   # digit -> pin
    for d in range(8):
        pins[digs[d]] = "COL%d" % (first + d + 1) if first + d < last else None
    segs = {0: "14", 1: "16", 2: "20", 3: "23", 4: "21", 5: "15", 6: "17"}        # SEG A..G -> pin
    for s in range(7):
        pins[segs[s]] = "ROW%s%d" % (tag, s + 1)
    part(ref, "Driver_LED:MAX7219", "MAX7219CWG+T", "Package_SO:SOIC-24W_7.5x15.4mm_P1.27mm", "C9964", pins,
         chip_x, 0.0, side="B", ok=True, mpn="MAX7219CWG+T", desc="8-digit LED driver (SPI), columns " + ("1-6" if tag == "A" else "7-11"))
    n = 2 if tag == "A" else 3
    two("R%d" % (8 + n), "R", "22k", R0603, "C31850", "+5V", "ISET_" + tag, chip_x + 3.6, 9.8, side="B", ok=False,
        mpn="0603WAF2202T5E", desc="MAX7219 ISET: sets LED current (~10-15 mA peak)")
    two("C%d" % (7 + 2 * n - 2), "C", "100n", C0603, "C14663", "+5V", "GND", chip_x - 3.6, 9.8, side="B", ok=False, mpn="CL10B104KB8NNNC", desc="Decoupling")
    two("C%d" % (7 + 2 * n - 1), "C", "10u", C0805, "C15850", "+5V", "GND", chip_x, 9.8, side="B", ok=False, mpn="CL21A106KAYNNNE", desc="Bulk capacitor")

# ---- the 77 LEDs (top side).  Cathode -> column (digit), anode -> row (segment)
LEDS = []
for i in range(COLS):
    for j in range(ROWS):
        n = len(LEDS) + 1
        tag = "A" if i < SPLIT else "B"
        LEDS.append(dict(ref="D%d" % (5 + n), col=i, row=j, kc="COL%d" % (i + 1), ka="ROW%s%d" % (tag, j + 1),
                         x=MATRIX_X0 + COL_PITCH * i, y=MATRIX_Y0 + ROW_PITCH * j))
for L in LEDS:
    part(L["ref"], "Device:LED", "Blue 0603", "LED_SMD:LED_0603_1608Metric", "C2288", {"1": L["kc"], "2": L["ka"]},
         L["x"], L["y"], ok=True, mpn="KT-0603B", desc="0603 blue LED (matrix)")

# ---------------------------------------------------------------- legend / art
SILK_TOP = []          # text on top is added by build_pcb.py (USB labels, logo box and the two 3 mm text lines)
SILK_BOT = [
    ("CircuitPath", 33.4, 0.0, 90, 1.6),
    ("Banyule Nillumbik", 35.6, 0.0, 90, 1.0),
    ("Tech School", 37.0, 0.0, 90, 1.0),
    ("RESET = short pads 5+6", 55.5, 3.8, 0, 0.7),
]
