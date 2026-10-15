"""Autorouting (Freerouting), copper pours and DRC for generated boards."""

import os
import re
import shutil
import subprocess

import pcbnew

MIN_TRACK = 0.15
JAVA = os.environ.get("VIBEDUINO_JAVA", shutil.which("java") or "java")
FREEROUTING = os.environ.get("FREEROUTING_JAR", "")


def _route_score(board):
    """(unconnected, clearance-type errors) as KiCad's own DRC sees them."""
    rpt = "/tmp/vibeduino-route.rpt"
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    os.remove(rpt)
    m = re.search(r"\*\* Found (\d+) unconnected pads \*\*", txt)
    errors = sum(1 for k in re.findall(r"^\[(\w+)\]", txt, re.M) if k in CLEARANCE_TYPES + ("track_width",))
    return (int(m.group(1)) if m else 0, errors)


def autoroute(pcb_path, passes=40, attempts=5, timeout=900):
    """Export Specctra DSN, run Freerouting headless (several attempts, it is not
    deterministic) and import the session that KiCad's DRC likes best."""
    if not FREEROUTING or not os.path.exists(FREEROUTING):
        raise RuntimeError("set FREEROUTING_JAR to freerouting-2.x-executable.jar")
    base = os.path.splitext(pcb_path)[0]
    dsn, ses = base + ".dsn", base + ".ses"
    if not pcbnew.ExportSpecctraDSN(pcbnew.LoadBoard(pcb_path), dsn):
        raise RuntimeError("DSN export failed")
    best = None
    for attempt in range(attempts):
        if os.path.exists(ses):
            os.remove(ses)
        log = subprocess.run([JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses,
                              f"--router.autorouter.max_passes={passes * (1 + attempt // 2)}",
                              "--router.neck_width_um=150", "--gui.enabled=false",
                              "--usage_and_diagnostic_data.disable_analytics=true"],
                             capture_output=True, text=True, timeout=timeout)
        if not os.path.exists(ses):
            raise RuntimeError("freerouting failed:\n" + log.stdout[-3000:] + log.stderr[-3000:])
        # pcbnew.ImportSpecctraSES() needs the GUI editor in KiCad 7, so the
        # session file is parsed here instead.
        trial = pcbnew.LoadBoard(pcb_path)
        n_wires, _ = import_ses(trial, ses)
        score = _route_score(trial) if n_wires else (10 ** 6, 0)
        if best is None or score < best[0]:
            best = (score, open(ses).read())
        if score == (0, 0):
            break
    with open(ses, "w") as f:
        f.write(best[1])
    board = pcbnew.LoadBoard(pcb_path)
    import_ses(board, ses)
    pcbnew.SaveBoard(pcb_path, board)
    for f in (dsn, ses):
        os.remove(f)
    for f in os.listdir(os.path.dirname(pcb_path) or "."):
        if f.endswith(".rules"):
            os.remove(os.path.join(os.path.dirname(pcb_path), f))
    return best[0]


def _sexpr(text):
    tokens = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def _find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            yield c


def import_ses(board, ses_path):
    """Add the wires and vias of a Specctra session file to ``board``."""
    root = _sexpr(open(ses_path).read())
    routes = next(_find(root, "routes"))
    res = next(_find(routes, "resolution"))
    per_mm = {"um": 1000.0, "mm": 1.0, "mil": 1 / 0.0254}[res[1]] * float(res[2])

    def xy(x, y):
        return pcbnew.VECTOR2I(pcbnew.FromMM(float(x) / per_mm), pcbnew.FromMM(-float(y) / per_mm))

    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    nets = board.GetNetsByName()
    # Pre-routed (locked) copper is exported as fixed wiring; skip duplicates.
    existing = set()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            existing.add(("via", t.GetPosition().x // 1000, t.GetPosition().y // 1000))
        else:
            a, b = t.GetStart(), t.GetEnd()
            key = tuple(sorted([(a.x // 1000, a.y // 1000), (b.x // 1000, b.y // 1000)]))
            existing.add((t.GetLayer(), key))
    n_wires = n_vias = 0
    for net in _find(next(_find(routes, "network_out")), "net"):
        ni = nets[net[1]] if net[1] in nets else None
        for wire in _find(net, "wire"):
            path = next(_find(wire, "path"))
            layer, width, coords = path[1], float(path[2]) / per_mm, path[3:]
            width = max(width, MIN_TRACK)          # neck-downs never below the fab minimum
            pts = [xy(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                key = tuple(sorted([(a.x // 1000, a.y // 1000), (b.x // 1000, b.y // 1000)]))
                if (layers[layer], key) in existing:
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a)
                t.SetEnd(b)
                t.SetWidth(pcbnew.FromMM(width))
                t.SetLayer(layers[layer])
                if ni:
                    t.SetNet(ni)
                board.Add(t)
                n_wires += 1
        for via in _find(net, "via"):
            m = re.search(r"_(\d+):(\d+)_um", via[1])
            pos = xy(via[2], via[3])
            if ("via", pos.x // 1000, pos.y // 1000) in existing:
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pos)
            v.SetWidth(pcbnew.FromMM(int(m.group(1)) / 1000))
            v.SetDrill(pcbnew.FromMM(int(m.group(2)) / 1000))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            if ni:
                v.SetNet(ni)
            board.Add(v)
            n_vias += 1
    return n_wires, n_vias


def drc(pcb_path):
    """Run DRC, return (errors, warnings, unconnected, report_text)."""
    board = pcbnew.LoadBoard(pcb_path)
    rpt = os.path.splitext(pcb_path)[0] + "-drc.rpt"
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    with open(rpt) as f:
        txt = f.read()
    items = re.findall(r"^\[(\w+)\]: .*\n\s+.*Severity: (\w+)", txt, re.M)
    items = [(k, sev) for k, sev in items if k not in ("lib_footprint_issues",
                                                        "lib_footprint_mismatch")]
    errors = sum(1 for _, sev in items if sev == "error")
    warnings = sum(1 for _, sev in items if sev == "warning")
    m = re.search(r"\*\* Found (\d+) unconnected pads \*\*", txt)
    unconnected = int(m.group(1)) if m else 0
    return errors, warnings, unconnected, txt


CLEARANCE_TYPES = ("clearance", "hole_clearance", "copper_edge_clearance", "tracks_crossing",
                   "shorting_items", "solder_mask_bridge")


def _seg_dist(px, py, t):
    ax, ay, bx, by = t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return ((ax + u * dx - px) ** 2 + (ay + u * dy - py) ** 2) ** 0.5


def _clearance_hits(board, nets):
    rpt = "/tmp/vibeduino-widen.rpt"
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    os.remove(rpt)
    hits = []
    for block in re.split(r"\n(?=\[)", txt):
        m = re.match(r"\[(\w+)\]", block)
        if not m or m.group(1) not in CLEARANCE_TYPES:
            continue
        for x, y, net, ln in re.findall(
                r"@\(([-\d.]+) mm, ([-\d.]+) mm\): Track \[([^\]]+)\] on \S+, length ([\d.]+) mm", block):
            if net in nets:
                hits.append((pcbnew.FromMM(float(x)), pcbnew.FromMM(float(y)), float(ln)))
    return hits


def widen_power(pcb_path, nets=("GND", "+5V", "+3V3"), widths=(0.4, 0.3)):
    """Freerouting 2.x routes every net at the default width.  Widen power nets
    to the Power netclass width, stepping back wherever DRC reports a clearance
    problem; anything still in conflict returns to the router's original width."""
    board = pcbnew.LoadBoard(pcb_path)
    tracks = [t for t in board.GetTracks()
              if t.GetClass() == "PCB_TRACK" and t.GetNetname() in nets]
    original = {id(t): t.GetWidth() for t in tracks}
    level = {id(t): 0 for t in tracks}

    def apply(t):
        k = level[id(t)]
        w = pcbnew.FromMM(widths[k]) if k < len(widths) else original[id(t)]
        t.SetWidth(max(original[id(t)], w))

    def near(hx, hy, ln, tol=pcbnew.FromMM(0.05)):
        c = [t for t in tracks if _seg_dist(hx, hy, t) < tol and abs(pcbnew.ToMM(t.GetLength()) - ln) < 0.01]
        return c or [t for t in tracks if _seg_dist(hx, hy, t) < tol]

    for t in tracks:
        apply(t)
    for _ in range(8):
        hits = _clearance_hits(board, nets)
        if not hits:
            break
        stepped = set()
        for hx, hy, ln in hits:
            for t in near(hx, hy, ln):
                if id(t) not in stepped:
                    stepped.add(id(t))
                    level[id(t)] += 1
                    apply(t)
    for hx, hy, ln in _clearance_hits(board, nets):        # last resort
        for t in tracks:
            if _seg_dist(hx, hy, t) < pcbnew.FromMM(1.0):
                t.SetWidth(original[id(t)])
    pcbnew.SaveBoard(pcb_path, board)
    wide = sum(1 for t in tracks if t.GetWidth() >= pcbnew.FromMM(widths[0]))
    return wide, len(tracks)
