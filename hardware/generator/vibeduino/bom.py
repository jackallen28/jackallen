"""Bill of materials: parts catalogue, footprint annotation and BOM/CPL writers.

The BOM is derived from the footprints actually placed on each .kicad_pcb so it
cannot drift from the layout.  Each footprint is matched against CATALOGUE by
footprint id and value; the match supplies the purchasable description,
manufacturer and part number, and the assembly process.

Process codes
  SMT   machine placed (reflow) - goes in the pick-and-place (CPL) file
  THT   through-hole, wave/hand soldered
  HAND  hand-assembled special part (OLED glass with solder FPC)
  -     board feature only (holes, test pads, solder jumper): not purchased
"""

import collections
import csv
import os

import pcbnew

# 1 % 0603 thick-film resistors: value -> (UNI-ROYAL MPN, LCSC/JLCPCB part).  All except 390k
# are JLCPCB "Basic" parts (no extended-part fee).
RES_0603 = {"10k": ("0603WAF1002T5E", "C25804"), "1k": ("0603WAF1001T5E", "C21190"),
            "220R": ("0603WAF2200T5E", "C22962"), "330R": ("0603WAF3300T5E", "C23138"),
            "470R": ("0603WAF4700T5E", "C23179"), "3.3k": ("0603WAF3301T5E", "C22978"),
            "4.7k": ("0603WAF4701T5E", "C23162"), "390k": ("0603WAF3903T5E", "C23150")}
RES_TEXT = {"10k": "10 kΩ", "1k": "1 kΩ", "220R": "220 Ω", "330R": "330 Ω", "470R": "470 Ω",
            "3.3k": "3.3 kΩ", "4.7k": "4.7 kΩ", "390k": "390 kΩ"}

# (value, footprint fragment) -> (manufacturer, MPN, description, LCSC)
CAPS = {
    ("100nF", "C_0603"): ("YAGEO", "CC0603KRX7R9BB104", "Capacitor 100 nF 50 V X7R 0603", "C14663"),
    ("1uF", "C_0603"): ("Samsung", "CL10A105KB8NNNC", "Capacitor 1 µF 50 V X5R 0603", "C15849"),
    ("2.2uF 16V", "C_0603"): ("Samsung", "CL10A225KO8NNNC", "Capacitor 2.2 µF 16 V X5R 0603",
                              "C23630"),
    ("4.7uF", "C_0603"): ("Samsung", "CL10A475KO8NNNC", "Capacitor 4.7 µF 16 V X5R 0603", "C19666"),
    ("10uF", "C_0805"): ("Samsung", "CL21A106KAYNNNE", "Capacitor 10 µF 25 V X5R 0805", "C15850"),
}

# lcsc: LCSC / JLCPCB part number (checked against the LCSC/JLCPCB listings, Oct 2026).
# Empty = commodity part with no verified listing; pick one to the description when ordering.
Part = collections.namedtuple("Part", "key desc mfr mpn package process note lcsc", defaults=("",))

CATALOGUE = [
    # (footprint-id substring, value or None, Part)
    ("SW_Push_1P1T_XKB_TS-1187A", None, Part(
        "SW-TACT-5.1", "Tactile switch SPST-NO, 5.1×5.1 mm SMD", "XKB Connection",
        "TS-1187A-B-A-B", "SMD 5.1×5.1", "SMT", "", "C318884")),
    ("LED_WS2812B_PLCC4_5.0x5.0mm", None, Part(
        "WS2812B", "Addressable RGB LED, 5050", "Worldsemi", "WS2812B-B/W", "PLCC4 5×5", "SMT", "",
        "C114586")),
    ("SOT-23", "BSS138", Part(
        "BSS138", "N-MOSFET 50 V 0.22 A (I2C level shifter)", "JSCJ", "BSS138", "SOT-23", "SMT", "",
        "C78284")),
    ("SOT-23", "MMBT3904", Part(
        "MMBT3904", "NPN transistor 40 V 0.2 A", "JSCJ", "MMBT3904", "SOT-23", "SMT", "",
        "C20526")),
    ("SOT-23", "MCP9700A-E/TT", Part(
        "MCP9700A", "Analog temperature sensor, 10 mV/°C, 500 mV @ 0 °C", "Microchip",
        "MCP9700AT-E/TT", "SOT-23", "SMT", "", "C127949")),
    ("D_SOD-323", None, Part(
        "1N4148WS", "Switching diode 75 V 150 mA", "JSCJ", "1N4148WS", "SOD-323", "SMT", "",
        "C2128")),
    ("LED_0603", "GREEN", Part(
        "LED-0603-G", "LED green 0603", "Hubei KENTO", "KT-0603G", "0603", "SMT", "", "C12624")),
    ("LED_0603", "RED", Part(
        "LED-0603-R", "LED red 0603", "Hubei KENTO", "KT-0603R", "0603", "SMT", "", "C2286")),
    ("CP_Elec_5x5.4", None, Part(
        "CAP-EL-100U-5", "Aluminium electrolytic 100 µF 10 V, SMD 5×5.4 mm", "ST(Semtech)",
        "CS1A101M-CRD54", "5×5.4", "SMT", "", "C96182")),
    ("CP_Elec_6.3x5.4", None, Part(
        "CAP-EL-100U-6", "Aluminium electrolytic 100 µF 16 V, SMD 6.3×5.4 mm", "ROQANG",
        "RVT1C101M0605", "6.3×5.4", "SMT", "", "C72475")),
    ("JST_SH_BM04B-SRSS-TB", None, Part(
        "QWIIC", "JST SH 4-pin 1.0 mm vertical (Qwiic / STEMMA QT)", "JST",
        "BM04B-SRSS-TB(LF)(SN)", "SMD", "SMT", "", "C160390")),
    ("LED_D5.0mm", "5mm RED diffused", Part(
        "LED-5-R", "LED 5 mm red, diffused", "any", "—", "THT 5 mm", "THT",
        "no verified listing: any 5 mm diffused red")),
    ("LED_D5.0mm", "5mm YELLOW diffused", Part(
        "LED-5-Y", "LED 5 mm yellow, diffused", "XINGLIGHT", "XL-504UYD", "THT 5 mm", "THT", "",
        "C2895495")),
    ("LED_D5.0mm", "5mm GREEN diffused", Part(
        "LED-5-G", "LED 5 mm green, diffused", "any", "—", "THT 5 mm", "THT",
        "no verified listing: any 5 mm diffused green")),
    ("Potentiometer_Alps_RK09K", None, Part(
        "POT-RK09K", "Rotary potentiometer 9 mm, 10 kΩ linear (B), vertical, with mounting tabs",
        "Alps Alpine", "RK09K1130A5R", "THT", "THT", "check shaft length; fit a knob", "C209779")),
    ("Buzzer_12x9.5RM7.6", None, Part(
        "BUZZER-12", "Passive magnetic buzzer (transducer) 12×9.5 mm, 5 V, ≥ 40 Ω, 7.6 mm pitch",
        "any", "— (passive, no oscillator)", "THT 12 mm", "THT",
        "must be PASSIVE so tone() works; no verified LCSC listing")),
    ("R_LDR_5.1x4.3mm", None, Part(
        "LDR-GL5528", "Photoresistor (LDR) 5 mm, 8–20 kΩ @ 10 lux", "Senba", "GL5528", "THT", "THT",
        "CdS - not EU-RoHS; phototransistor alternative", "C125627")),
    ("PinHeader_1x05_P2.54mm", None, Part(
        "HDR-M-1x05", "Pin header 1×5, 2.54 mm, straight", "XFCN", "PZ254V-11-05P", "THT", "THT",
        "module bus: fit on the UNDERSIDE, pins down", "C492404")),
    ("PinHeader_1x03_P2.54mm", None, Part(
        "HDR-M-1x03", "Pin header 1×3, 2.54 mm, straight", "XFCN", "PZ254V-11-03P", "THT", "THT",
        "servo plug", "C2937625")),
    ("PinHeader_1x06_P2.54mm", None, Part(
        "HDR-M-1x06", "Pin header 1×6, 2.54 mm, straight", "XFCN", "PZ254V-11-06P", "THT", "THT",
        "Arduino header: fit on the UNDERSIDE", "C492405")),
    ("PinHeader_1x08_P2.54mm", None, Part(
        "HDR-M-1x08", "Pin header 1×8, 2.54 mm, straight", "XFCN", "PZ254V-11-08P", "THT", "THT",
        "Arduino header: fit on the UNDERSIDE", "C492407")),
    ("PinHeader_1x10_P2.54mm", None, Part(
        "HDR-M-1x10", "Pin header 1×10, 2.54 mm, straight", "XFCN", "PZ254V-11-10P", "THT", "THT",
        "Arduino header: fit on the UNDERSIDE", "C492409")),
    ("PinSocket_1x05_P2.54mm", None, Part(
        "HDR-F-1x05", "Female socket 1×5, 2.54 mm, 8.5 mm tall", "BOOMELE", "2.54-1*5PFemale", "THT",
        "THT", "module slot; trim leads to <= 1.5 mm", "C50950")),
    ("OLED_0.66in_64x48", None, Part(
        "OLED-0.66", "OLED 0.66\" 64×48, SSD1306, 28-pin solder FPC (glass folds over pads)", "—",
        "panel used on SparkFun LCD-22495 (verify supplier drawing)", "FPC", "HAND",
        "solder FPC by hand / hot-bar; tape glass down")),
    ("SolderJumper", None, None),
    ("VIBEDUINO:NPTH", None, None),
    ("VIBEDUINO:BusBreakout", None, None),
    ("VIBEDUINO:ProtoGrid", None, None),
]


def classify(fp):
    fpid, value = fp.GetFPIDAsString(), fp.GetValue()
    if fp.GetReference().startswith("KiKit_"):
        return None                    # panel fiducials, tooling and mouse-bite holes
    if "R_0603" in fpid:
        mpn, lcsc = RES_0603[value]
        return Part(f"R-0603-{value}", f"Resistor {RES_TEXT[value]} 1 % 0603", "UNI-ROYAL",
                    mpn, "0603", "SMT", "", lcsc)
    for (val, frag), (mfr, mpn, desc, lcsc) in CAPS.items():
        if frag in fpid and value == val:
            return Part(f"C-{frag}-{val}", desc, mfr, mpn, frag.split("_")[1], "SMT", "", lcsc)
    for frag, val, part in CATALOGUE:
        if frag in fpid and (val is None or val == value):
            return part
    raise KeyError(f"no catalogue entry for {fp.GetReference()} {fpid} {value}")


# JLCPCB's part library draws some packages rotated relative to KiCad's footprints.  Offsets
# (degrees, added for top-side parts) for the packages used here, after the widely used
# community rotation tables.  Always confirm in JLCPCB's placement preview.
JLC_ROTATION = [("SOT-23", 180), ("CP_Elec_", 180), ("LED_WS2812B_PLCC4", 180)]


def jlc_rotation(fp):
    rot = fp.GetOrientationDegrees() % 360
    name = str(fp.GetFPID().GetLibItemName())
    corr = next((c for frag, c in JLC_ROTATION if frag in name), 0)
    if fp.IsFlipped():
        # JLCPCB reads bottom-side parts as seen from the top: mirror about the Y axis
        return (180 - rot - corr) % 360
    return (rot + corr) % 360


def annotate(pcb_path):
    """Write MPN/manufacturer/description fields into each footprint and set the
    exclude-from-BOM / exclude-from-placement attributes for board features."""
    board = pcbnew.LoadBoard(pcb_path)
    for fp in board.GetFootprints():
        part = classify(fp)
        attrs = fp.GetAttributes()
        if part is None:
            attrs |= pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
        else:
            fp.SetProperty("Description", part.desc)
            fp.SetProperty("Manufacturer", part.mfr)
            fp.SetProperty("MPN", part.mpn)
            fp.SetProperty("Process", part.process)
            if part.lcsc:
                fp.SetProperty("LCSC", part.lcsc)
            if part.process != "SMT":
                attrs |= pcbnew.FP_EXCLUDE_FROM_POS_FILES
        fp.SetAttributes(attrs)
    pcbnew.SaveBoard(pcb_path, board)


def board_lines(pcb_path):
    """Grouped BOM lines for one board."""
    board = pcbnew.LoadBoard(pcb_path)
    groups = collections.OrderedDict()
    for fp in sorted(board.GetFootprints(), key=lambda f: _refkey(f.GetReference())):
        part = classify(fp)
        if part is None:
            continue
        side = "Bottom" if fp.IsFlipped() else "Top"
        g = groups.setdefault((part.key, side), dict(part=part, refs=[], side=side,
                                                      footprint=fp.GetFPIDAsString()))
        g["refs"].append(fp.GetReference())
    return list(groups.values())


def _refkey(ref):
    head = ref.rstrip("0123456789")
    tail = ref[len(head):]
    return head, int(tail) if tail else 0


def ascii(text):
    """JLCPCB's BOM importer is happiest with plain ASCII."""
    for a, b in (("Ω", "ohm"), ("µ", "u"), ("×", "x"), ("°", "deg"), ("–", "-"), ("—", "-"),
                 ("≥", ">="), ("≤", "<=")):
        text = text.replace(a, b)
    return text


def write_board_bom(pcb_path, out_dir, name):
    lines = board_lines(pcb_path)
    os.makedirs(out_dir, exist_ok=True)
    full = os.path.join(out_dir, f"{name}-bom.csv")
    with open(full, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Designators", "Description", "Manufacturer", "MPN", "LCSC", "Package",
                    "Side", "Process", "Notes", "KiCad footprint"])
        for g in lines:
            p = g["part"]
            w.writerow([len(g["refs"]), " ".join(g["refs"]), p.desc, p.mfr, p.mpn, p.lcsc,
                        p.package, g["side"], p.process, p.note, g["footprint"]])
    # JLCPCB assembly BOM: every part JLCPCB can fit, SMT and through-hole (untick the
    # through-hole lines in JLCPCB's BOM check to hand-solder them instead).
    jlc = os.path.join(out_dir, f"{name}-bom-jlcpcb.csv")
    merged = collections.OrderedDict()
    for g in lines:
        if g["part"].process in ("SMT", "THT"):
            merged.setdefault(g["part"].key, dict(part=g["part"], refs=[]))["refs"] += g["refs"]
    with open(jlc, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for g in merged.values():
            p = g["part"]
            w.writerow([ascii(p.desc if p.mpn.startswith("—") else f"{p.desc} ({p.mpn})"),
                        ",".join(g["refs"]), ascii(p.package), p.lcsc])
    return lines


def placement_rows(pcb_path):
    """(designator, x mm, y mm, side, JLCPCB rotation, process) for every SMT/THT part.
    Y is flipped to the usual CAM orientation (up = +Y), matching the Gerbers."""
    board = pcbnew.LoadBoard(pcb_path)
    rows = []
    for fp in sorted(board.GetFootprints(), key=lambda f: _refkey(f.GetReference())):
        part = classify(fp)
        if part is None or part.process not in ("SMT", "THT"):
            continue
        if part.process == "THT":
            # header footprints have their origin on pin 1; place by the body centre instead
            box = None
            for pad in fp.Pads():
                b = pad.GetBoundingBox()
                if box is None:
                    box = b
                else:
                    box.Merge(b)
            c = box.GetCenter()
        else:
            c = fp.GetPosition()
        rows.append((fp.GetReference(), pcbnew.ToMM(c.x), -pcbnew.ToMM(c.y),
                     "Bottom" if fp.IsFlipped() else "Top", jlc_rotation(fp), part.process))
    return rows


def write_cpl(pcb_path, out_dir, name):
    """JLCPCB pick-and-place (CPL) file, with JLCPCB rotation offsets applied."""
    rows = placement_rows(pcb_path)
    out = os.path.join(out_dir, f"{name}-cpl-jlcpcb.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref, x, y, side, rot, _ in rows:
            w.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", side, f"{rot:.1f}"])
    return sum(1 for r in rows if r[5] == "SMT")
