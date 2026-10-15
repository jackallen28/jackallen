"""Schematic generation from the routed PCB netlists.

Each board gets a KiCad 7 schematic built from its own .kicad_pcb: every
footprint becomes a library symbol whose pin numbers match the footprint pads,
every pin gets a short wire and a net label (or a no-connect flag), the power
nets get one power-symbol block, and the result is checked by exporting the
schematic netlist with kicad-cli and comparing it pin-for-pin with the PCB.
Schematics are therefore "net-label style": readable, editable in KiCad, and
guaranteed to match the layout.  UUIDs are derived from the project name, so
regenerating gives identical files, and the PCB footprints are linked to their
symbols so "Update PCB from Schematic" works in KiCad.
"""

import copy
import datetime
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid as _uuid

import pcbnew

from . import bom, spec
from .sexpr import Q, dump, find, first, parse

SYMDIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
GRID = 1.27
POWER = {"GND": "GND", "+5V": "+5V", "+3V3": "+3V3"}

# footprint id fragment, value (or None), (library, symbol); None = board-only item
SYMBOL_MAP = [
    ("R_0603", None, ("Device", "R")),
    ("C_0603", None, ("Device", "C")),
    ("C_0805", None, ("Device", "C")),
    ("CP_Elec", None, ("Device", "C_Polarized")),
    ("LED_0603", None, ("Device", "LED")),
    ("LED_D5.0mm", None, ("Device", "LED")),
    ("D_SOD-323", None, ("Device", "D")),
    ("R_LDR", None, ("Device", "R_Photo")),
    ("Potentiometer_Alps_RK09K", None, ("Device", "R_Potentiometer_MountingPin")),
    ("Buzzer_12x9.5", None, ("Device", "Buzzer")),
    ("SW_Push_1P1T_XKB_TS-1187A", None, ("Switch", "SW_Push")),
    ("SOT-23", "BSS138", ("Transistor_FET", "BSS138")),
    ("SOT-23", "MMBT3904", ("Transistor_BJT", "MMBT3904")),
    ("SOT-23", "MCP9700A-E/TT", ("Sensor_Temperature", "MCP9700Ax-ETT")),
    ("LED_WS2812B", None, ("LED", "WS2812B")),
    ("PinHeader_1x03", None, ("Connector_Generic", "Conn_01x03")),
    ("PinHeader_1x05", None, ("Connector_Generic", "Conn_01x05")),
    ("PinSocket_1x05", None, ("Connector_Generic", "Conn_01x05")),
    ("PinHeader_1x06", None, ("Connector_Generic", "Conn_01x06")),
    ("PinHeader_1x08", None, ("Connector_Generic", "Conn_01x08")),
    ("PinHeader_1x10", None, ("Connector_Generic", "Conn_01x10")),
    ("JST_SH_BM04B", None, ("Connector_Generic_MountingPin", "Conn_01x04_MountingPin")),
    ("SolderJumper", None, ("Jumper", "SolderJumper_2_Open")),
    ("OLED_0.66in", None, ("VIBEDUINO", "OLED_0.66in_SSD1306_FPC28")),
    ("BusBreakout", None, ("VIBEDUINO", "BusBreakout")),
    ("VIBEDUINO:NPTH", None, None),
    ("ProtoGrid", None, None),
]

OLED_PINS = ["GND", "C2P", "C2N", "C1P", "C1N", "VBAT", "VSS", "VDD", "BS1", "BS2", "~{CS}",
             "~{RES}", "D/~{C}", "R/~{W}", "E/~{RD}", "D0/SCL", "D1/SDA_IN", "D2/SDA_OUT", "D3",
             "D4", "D5", "D6", "D7", "IREF", "VCOMH", "VCC", "VLSS", "GND"]


_UID = {"seed": "", "n": 0}


def _det_uuid(*parts):
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, "vibeduino/" + "/".join(parts)))


def uid():
    """Deterministic per-sheet UUIDs (stable across regeneration)."""
    _UID["n"] += 1
    return _det_uuid(_UID["seed"], str(_UID["n"]))


# ----------------------------------------------------------------- libraries
_LIBS = {}


def _lib(name):
    if name not in _LIBS:
        _LIBS[name] = parse(open(os.path.join(SYMDIR, name + ".kicad_sym")).read())[0]
    return _LIBS[name]


def _raw_symbol(lib, name):
    for s in find(_lib(lib), "symbol"):
        if s[1] == name:
            return s
    raise KeyError(f"{lib}:{name}")


def library_symbol(lib, name):
    """Flattened symbol definition (extends resolved), named 'lib:name'."""
    if lib == "VIBEDUINO":
        sym = custom_symbol(name)
    else:
        sym = copy.deepcopy(_raw_symbol(lib, name))
        ext = first(sym, "extends")
        if ext:
            base = copy.deepcopy(_raw_symbol(lib, ext[1]))
            props = {p[1]: p for p in find(sym, "property")}
            node = [c if not (isinstance(c, list) and c[0] == "property" and c[1] in props)
                    else props[c[1]] for c in base]
            for c in node:
                if isinstance(c, list) and c[0] == "symbol":
                    c[1] = Q(str(c[1]).replace(str(ext[1]), name, 1))
            sym = node
    sym = copy.deepcopy(sym)
    sym[1] = Q(f"{lib}:{name}")
    return sym


def custom_symbol(name):
    """VIBEDUINO-specific symbols (the OLED panel and the PROTO breakout)."""
    if name == "OLED_0.66in_SSD1306_FPC28":
        pins = [(str(n), OLED_PINS[n - 1]) for n in range(1, 29)]
        ref, val, fpid = "DS", "OLED_0.66in_64x48", "VIBEDUINO:OLED_0.66in_64x48_FPC28"
    elif name == "BusBreakout":
        pins = [(f"{h}{i + 1}", spec.BUS_LABELS[n]) for h, nets in (("J1", spec.BUS_J1), ("J2", spec.BUS_J2))
                for i, n in enumerate(nets)]
        ref, val, fpid = "TP", "BusBreakout", "VIBEDUINO:BusBreakout"
    else:
        raise KeyError(name)
    half = (len(pins) + 1) // 2
    h = (half + 1) * 2.54
    w = 15.24 if name.startswith("OLED") else 12.7
    body = [Q(name + "_0_1"), ["rectangle", ["start", -w / 2, h / 2], ["end", w / 2, -h / 2],
                                ["stroke", ["width", 0.254], ["type", "default"]],
                                ["fill", ["type", "background"]]]]
    pin_nodes = [Q(name + "_1_1")]
    for i, (num, pname) in enumerate(pins):
        left = i < half
        row = i if left else i - half
        x = -w / 2 - 2.54 if left else w / 2 + 2.54
        y = h / 2 - 2.54 * (row + 1)
        pin_nodes.append(["pin", "passive", "line", ["at", x, y, 0 if left else 180], ["length", 2.54],
                          ["name", Q(pname), ["effects", ["font", ["size", 1.016, 1.016]]]],
                          ["number", Q(num), ["effects", ["font", ["size", 1.016, 1.016]]]]])
    sym = ["symbol", Q(name), ["in_bom", "yes"], ["on_board", "yes"],
           _prop("Reference", ref, 0, h / 2 + 1.27), _prop("Value", val, 0, -h / 2 - 1.27),
           _prop("Footprint", fpid, 0, 0, hide=True), _prop("Datasheet", "~", 0, 0, hide=True),
           ["symbol"] + body, ["symbol"] + pin_nodes]
    return sym


def write_custom_library(path):
    lib = ["kicad_symbol_lib", ["version", 20220914], ["generator", "vibeduino"]]
    for n in ("OLED_0.66in_SSD1306_FPC28", "BusBreakout"):
        lib.append(custom_symbol(n))
    with open(path, "w") as f:
        f.write(dump(lib) + "\n")


def _prop(name, value, x, y, hide=False, justify=None, angle=0):
    eff = ["effects", ["font", ["size", 1.27, 1.27]]]
    if justify:
        eff.append(["justify", justify])
    if hide:
        eff.append("hide")
    return ["property", Q(name), Q(value), ["at", x, y, angle], eff]


def symbol_pins(sym):
    """[(number, name, x, y, angle, length)] in symbol coordinates (y up), unit 1, style 1."""
    pins = []
    name = str(sym[1]).split(":", 1)[-1]
    for sub in find(sym, "symbol"):
        tag = str(sub[1])
        if not (tag.endswith("_0_1") or tag.endswith("_1_1") or tag.endswith("_0_0")
                or tag.endswith("_1_0")):
            continue
        for p in find(sub, "pin"):
            at, ln = first(p, "at"), first(p, "length")
            pins.append((str(first(p, "number")[1]), str(first(p, "name")[1]), float(at[1]),
                         float(at[2]), int(float(at[3])), float(ln[1])))
    if not pins:
        raise ValueError(f"no pins in {name}")
    return pins


def symbol_bbox(sym):
    xs, ys = [], []

    def walk(n):
        if not isinstance(n, list) or not n:
            return
        k = n[0]
        if k in ("start", "end", "mid", "center", "xy") and len(n) >= 3:
            try:
                xs.append(float(n[1]))
                ys.append(float(n[2]))
            except ValueError:
                pass
        if k == "property":
            return
        for c in n[1:]:
            walk(c)
    for sub in find(sym, "symbol"):
        walk(sub)
    for _, _, x, y, a, ln in symbol_pins(sym):
        xs += [x, x + ln * math.cos(math.radians(a))]
        ys += [y, y + ln * math.sin(math.radians(a))]
    # convert to schematic (y down)
    return min(xs), -max(ys), max(xs), -min(ys)


# ---------------------------------------------------------------- the board
def symbol_for(fp):
    fpid, value = fp.GetFPIDAsString(), fp.GetValue()
    for frag, val, target in SYMBOL_MAP:
        if frag in fpid and (val is None or val == value):
            return target
    raise KeyError(f"no symbol for {fp.GetReference()} {fpid}")


def _snap(v):
    return round(v / GRID) * GRID


def _ref_order(ref):
    head = ref.rstrip("0123456789")
    order = {"J": 0, "DS": 1, "U": 1, "Q": 2, "SW": 3, "RV": 3, "BZ": 3, "TP": 0, "D": 4, "R": 5,
             "C": 6, "JP": 7}
    tail = ref[len(head):]
    return order.get(head, 8), head, int(tail) if tail else 0


def build(pcb_path, sch_path, project, title, description):
    """Write the schematic; returns (n_symbols, paper, {ref: symbol uuid})."""
    new_sheet(project)
    board = pcbnew.LoadBoard(pcb_path)
    comps, used_syms = [], {}
    for fp in sorted(board.GetFootprints(), key=lambda f: _ref_order(f.GetReference())):
        target = symbol_for(fp)
        if target is None:
            continue
        lib_id = f"{target[0]}:{target[1]}"
        if lib_id not in used_syms:
            used_syms[lib_id] = library_symbol(*target)
        sym = used_syms[lib_id]
        pins = symbol_pins(sym)
        pad_net = {}
        for pad in fp.Pads():
            n = pad.GetNumber()
            if n:
                pad_net.setdefault(n, pad.GetNetname())
        missing = set(pad_net) - {p[0] for p in pins}
        if missing:
            raise ValueError(f"{fp.GetReference()}: symbol {lib_id} lacks pins {missing}")
        part = bom.classify(fp)
        comps.append(dict(ref=fp.GetReference(), lib_id=lib_id, sym=sym, pins=pins, nets=pad_net,
                          value=fp.GetValue(), footprint=fp.GetFPIDAsString(), part=part,
                          bbox=symbol_bbox(sym), dnp=part is None))
    net_size = {}
    for c in comps:
        for n in c["nets"].values():
            net_size[n] = net_size.get(n, 0) + 1

    # ---- layout: flow the parts into rows, leaving room for labels and ref/value text
    def plan(c):
        """Extent (incl. labels and ref/value) and ref/value anchors, relative to the symbol origin."""
        x0, y0, x1, y1 = c["bbox"]
        grow = dict(l=0, r=0, u=0, d=0)
        for num, _, px, py, a, _ in c["pins"]:
            net = c["nets"].get(num, "")
            text = 0 if not net or net.startswith("unconnected") else len(net) * 1.0 + 1.5
            side = {0: "l", 180: "r", 90: "d", 270: "u"}[a]
            grow[side] = max(grow[side], 2.54 + text)
        tw = max(len(c["ref"]), len(c["value"])) * 1.05
        if grow["l"] and grow["r"]:
            # pins on both sides (ICs): reference above the body, value below it
            cx = (x0 + x1) / 2
            ref = (cx, y0 - grow["u"] - 1.5, None)
            val = (cx, y1 + grow["d"] + 2.8, None)
            ext = (min(x0 - grow["l"], cx - tw / 2), y0 - grow["u"] - 3.5,
                   max(x1 + grow["r"], cx + tw / 2), y1 + grow["d"] + 4.0)
        else:
            tx, ty = x1 + max(grow["r"], 0.5) + 1.0, (y0 + y1) / 2
            ref = (tx, ty - 1.2, "left")
            val = (tx, ty + 1.2, "left")
            ext = (x0 - grow["l"], min(y0 - grow["u"], ty - 3.0) - 1.0,
                   tx + tw, max(y1 + grow["d"], ty + 2.5) + 1.0)
        return ext, ref, val

    for paper, (pw, ph) in (("A4", (297, 210)), ("A3", (420, 297))):
        x_lim, y_lim = pw - 15, ph - 45
        x, y, row_h, placed = 20.0, 42.0, 0.0, []
        for c in comps:
            ex = plan(c)[0]
            w, h = ex[2] - ex[0], ex[3] - ex[1]
            if x + w > x_lim and x > 20.0:
                x, y, row_h = 20.0, y + row_h + 6.0, 0.0
            placed.append((c, _snap(x - ex[0]), _snap(y - ex[1])))
            x += w + 6.0
            row_h = max(row_h, h)
        if y + row_h <= y_lim:
            break

    items, sym_uuids = [], {}
    for c, ox, oy in placed:
        sym_uuids[c["ref"]] = _det_uuid(project, "symbol", c["ref"])
        _, (rx, ry, rj), (vx, vy, vj) = plan(c)
        props = [_prop("Reference", c["ref"], ox + rx, oy + ry, justify=rj),
                 _prop("Value", c["value"], ox + vx, oy + vy, justify=vj),
                 _prop("Footprint", c["footprint"], ox, oy, hide=True),
                 _prop("Datasheet", "~", ox, oy, hide=True)]
        if c["part"]:
            props += [_prop("Description", c["part"].desc, ox, oy, hide=True),
                      _prop("Manufacturer", c["part"].mfr, ox, oy, hide=True),
                      _prop("MPN", c["part"].mpn, ox, oy, hide=True)]
            if c["part"].lcsc:
                props.append(_prop("LCSC", c["part"].lcsc, ox, oy, hide=True))
        node = ["symbol", ["lib_id", Q(c["lib_id"])], ["at", ox, oy, 0], ["unit", 1],
                ["in_bom", "no" if c["dnp"] else "yes"], ["on_board", "yes"], ["dnp", "no"],
                ["uuid", Q(sym_uuids[c["ref"]])]] + props
        node += [["pin", Q(p[0]), ["uuid", Q(uid())]] for p in c["pins"]]
        node.append(["instances", ["project", Q(project), ["path", Q("/" + ROOT_UUID[0]),
                                                           ["reference", Q(c["ref"])], ["unit", 1]]]])
        items.append(node)
        for num, _, px, py, a, _ in c["pins"]:
            cx, cy = ox + px, oy - py
            dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[a]
            net = c["nets"].get(num)
            if not net or net.startswith("unconnected"):
                items.append(["no_connect", ["at", cx, cy], ["uuid", Q(uid())]])
                continue
            ex, ey = cx + dx * 2.54, cy + dy * 2.54
            items.append(["wire", ["pts", ["xy", cx, cy], ["xy", ex, ey]],
                          ["stroke", ["width", 0], ["type", "default"]], ["uuid", Q(uid())]])
            ang = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[(dx, dy)]
            just = "left bottom" if ang in (0, 90) else "right bottom"
            items.append(["label", Q(net), ["at", ex, ey, ang], ["fields_autoplaced"],
                          ["effects", ["font", ["size", 1.27, 1.27]], ["justify"] + just.split()],
                          ["uuid", Q(uid())]])

    used_power = sorted({n for c in comps for n in c["nets"].values() if n in POWER})
    for i, net in enumerate(used_power):
        bx, by = _snap(pw - 70 + 18 * i), _snap(26.0)
        lib_id = f"power:{POWER[net]}"
        if lib_id not in used_syms:
            used_syms[lib_id] = library_symbol("power", POWER[net])
        down = net == "GND"
        ey = by + (3.81 if down else -3.81)
        items.append(["label", Q(net), ["at", bx, by, 0], ["fields_autoplaced"],
                      ["effects", ["font", ["size", 1.27, 1.27]], ["justify", "left", "bottom"]],
                      ["uuid", Q(uid())]])
        items.append(["wire", ["pts", ["xy", bx, by], ["xy", bx, ey]],
                      ["stroke", ["width", 0], ["type", "default"]], ["uuid", Q(uid())]])
        ref = f"#PWR{i + 1:02d}"
        items.append(["symbol", ["lib_id", Q(lib_id)], ["at", bx, ey, 0], ["unit", 1],
                      ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["uuid", Q(uid())],
                      _prop("Reference", ref, bx, ey, hide=True),
                      _prop("Value", net, bx, ey + (4.4 if down else -3.2)),
                      _prop("Footprint", "", bx, ey, hide=True), _prop("Datasheet", "", bx, ey, hide=True),
                      ["pin", Q("1"), ["uuid", Q(uid())]],
                      ["instances", ["project", Q(project), ["path", Q("/" + ROOT_UUID[0]),
                                                             ["reference", Q(ref)], ["unit", 1]]]]])

    today = datetime.date.today().isoformat()
    notes = [["text", Q(line), ["at", 20, 18 + 3.2 * i, 0],
              ["effects", ["font", ["size", 2.0 if i == 0 else 1.4, 2.0 if i == 0 else 1.4]] +
               (["bold"] if i == 0 else []), ["justify", "left", "bottom"]], ["uuid", Q(uid())]]
             for i, line in enumerate([title, description,
                                       "Auto-generated from the routed PCB netlist (net-label style): "
                                       "pins sharing a label are connected. Values/MPNs from bom.py."])]
    sch = ["kicad_sch", ["version", 20230121], ["generator", "eeschema"], ["uuid", Q(ROOT_UUID[0])],
           ["paper", Q(paper)],
           ["title_block", ["title", Q(title)], ["date", Q(today)], ["rev", Q("A")],
            ["company", Q("Allentronics Education Services - www.allentronics.com.au")],
            ["comment", 1, Q("VIBEDUINO - hex modules for Arduino Uno")]],
           ["lib_symbols"] + list(used_syms.values())] + notes + items + \
          [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]]
    with open(sch_path, "w") as f:
        f.write(dump(sch) + "\n")
    return len(comps), paper, sym_uuids


ROOT_UUID = [_det_uuid("root")]


def new_sheet(seed):
    _UID.update(seed=seed, n=0)
    ROOT_UUID[0] = _det_uuid(seed, "root")


def link_footprints(pcb_path, sch_file, sym_uuids):
    """Point every footprint at its schematic symbol (KiCad's symbol<->footprint link), and mark
    footprints that have no symbol (mounting holes, proto grid) as board-only."""
    board = pcbnew.LoadBoard(pcb_path)
    for fp in board.GetFootprints():
        u = sym_uuids.get(fp.GetReference())
        if u:
            fp.SetPath(pcbnew.KIID_PATH("/" + u))
            fp.SetProperty("Sheetname", "")
            fp.SetProperty("Sheetfile", sch_file)
        elif symbol_for(fp) is None:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY)
        else:
            raise KeyError(f"{fp.GetReference()} has no symbol in {sch_file}")
    pcbnew.SaveBoard(pcb_path, board)


# -------------------------------------------------------- project libraries
def write_libraries(lib_dir, pcb_paths):
    """kicad/lib: the custom symbols and the custom (VIBEDUINO:*) footprints used on the boards."""
    os.makedirs(lib_dir, exist_ok=True)
    write_custom_library(os.path.join(lib_dir, "vibeduino.kicad_sym"))
    pretty = os.path.join(lib_dir, "VIBEDUINO.pretty")
    os.makedirs(pretty, exist_ok=True)
    tmp = tempfile.mkdtemp()
    stage = os.path.join(tmp, "VIBEDUINO.pretty")
    pcbnew.FootprintLibCreate(stage)
    done = set()
    for path in pcb_paths:
        board = pcbnew.LoadBoard(path)
        for fp in board.GetFootprints():
            fpid = fp.GetFPID()
            name = str(fpid.GetLibItemName())
            if str(fpid.GetLibNickname()) != "VIBEDUINO" or name in done:
                continue
            done.add(name)
            lib_fp = pcbnew.FOOTPRINT(fp)
            if lib_fp.IsFlipped():
                lib_fp.Flip(lib_fp.GetPosition(), False)
            lib_fp.SetOrientationDegrees(0)
            lib_fp.SetPosition(pcbnew.VECTOR2I(0, 0))
            lib_fp.SetReference("REF**")
            lib_fp.SetPath(pcbnew.KIID_PATH())
            lib_fp.SetProperties({})      # BOM/sheet fields belong to the board, not the library
            pcbnew.FootprintSave(stage, lib_fp)
    # copy over only real changes (KiCad gives every saved item a fresh tstamp)
    strip = lambda t: re.sub(r"\(tstamp [0-9a-f-]+\)", "", t)
    for f in os.listdir(pretty):
        if f.endswith(".kicad_mod") and not os.path.exists(os.path.join(stage, f)):
            os.remove(os.path.join(pretty, f))
    for f in os.listdir(stage):
        new_text = open(os.path.join(stage, f)).read()
        dst = os.path.join(pretty, f)
        if not os.path.exists(dst) or strip(open(dst).read()) != strip(new_text):
            with open(dst, "w") as out:
                out.write(new_text)
    shutil.rmtree(tmp)
    return sorted(done)


def write_lib_tables(project_dir, lib_dir):
    """Project-local sym-lib-table / fp-lib-table pointing at kicad/lib."""
    rel = os.path.relpath(lib_dir, project_dir).replace(os.sep, "/")
    with open(os.path.join(project_dir, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (lib (name "VIBEDUINO")(type "KiCad")'
                f'(uri "${{KIPRJMOD}}/{rel}/vibeduino.kicad_sym")(options "")'
                '(descr "VIBEDUINO custom symbols"))\n)\n')
    with open(os.path.join(project_dir, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (lib (name "VIBEDUINO")(type "KiCad")'
                f'(uri "${{KIPRJMOD}}/{rel}/VIBEDUINO.pretty")(options "")'
                '(descr "VIBEDUINO custom footprints"))\n)\n')


# ------------------------------------------------------------- verification
def schematic_netlist(sch_path):
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "n.net")
        r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o",
                            out, sch_path], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError("netlist export failed: " + r.stdout + r.stderr)
        tree = parse(open(out).read())[0]
    nets = {}
    for net in find(first(tree, "nets"), "net"):
        name = str(first(net, "name")[1]).lstrip("/")
        nodes = {(str(first(n, "ref")[1]), str(first(n, "pin")[1])) for n in find(net, "node")}
        nets[name] = nodes
    comps = {str(first(c, "ref")[1]): str(first(c, "footprint")[1])
             for c in find(first(tree, "components"), "comp")}
    return nets, comps


def compare(pcb_path, sch_path):
    """Return a list of differences between PCB pad nets and schematic nets."""
    board = pcbnew.LoadBoard(pcb_path)
    pcb = {}
    pcb_fp = {}
    for fp in board.GetFootprints():
        if symbol_for(fp) is None:
            continue
        pcb_fp[fp.GetReference()] = fp.GetFPIDAsString()
        for pad in fp.Pads():
            if pad.GetNumber() and pad.GetNetname():
                pcb.setdefault(pad.GetNetname(), set()).add((fp.GetReference(), pad.GetNumber()))
    sch, sch_fp = schematic_netlist(sch_path)
    diffs = []
    # connectivity: every multi-pin PCB net must be exactly one schematic net
    node_net = {n: name for name, nodes in sch.items() for n in nodes}
    for name, nodes in pcb.items():
        if len(nodes) < 2:
            continue
        names = {node_net.get(n) for n in nodes}
        if len(names) != 1 or None in names:
            diffs.append(f"net {name}: split/missing in schematic {sorted(names, key=str)}")
            continue
        sname = names.pop()
        if sch[sname] != nodes:
            diffs.append(f"net {name}: schematic has extra {sorted(sch[sname] - nodes)}")
        if sname != name:
            diffs.append(f"net {name}: named {sname} in schematic")
    for ref, fpid in pcb_fp.items():
        if sch_fp.get(ref) != fpid:
            diffs.append(f"{ref}: footprint {sch_fp.get(ref)} != {fpid}")
    return diffs
