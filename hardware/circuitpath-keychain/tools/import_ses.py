"""Add the tracks and vias from a Freerouting .ses file to a KiCad 7 board (its Python API can't import SES in scripts).
python3 import_ses.py in.kicad_pcb routes.ses out.kicad_pcb"""
import re, sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew


def parse(text):
    toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    pos = 0

    def node():
        nonlocal pos
        out = []
        while pos < len(toks):
            t = toks[pos]; pos += 1
            if t == "(":
                out.append(node())
            elif t == ")":
                return out
            else:
                out.append(t.strip('"'))
        return out
    return node()


def find(n, key):
    for c in n:
        if isinstance(c, list) and c and c[0] == key:
            return c


def main(src, ses, dst):
    b = pcbnew.LoadBoard(src)
    tree = parse(open(ses).read())[0]
    res = find(tree, "routes")
    scale = 1e-4                                   # (resolution um 10): one unit is 0.1 um = 1e-4 mm
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    n_tr = n_via = 0
    have_via_mm = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    have_via = {(v.GetPosition().x // 1000, v.GetPosition().y // 1000) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T}
    have_seg = {(t.GetLayer(), t.GetStart().x // 1000, t.GetStart().y // 1000, t.GetEnd().x // 1000, t.GetEnd().y // 1000) for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T}
    for net in find(res, "network_out")[1:]:
        if not (isinstance(net, list) and net and net[0] == "net"):
            continue
        ni = b.FindNet(net[1])
        assert ni is not None, "unknown net " + net[1]
        for item in net[2:]:
            if not isinstance(item, list):
                continue
            if item[0] == "wire":
                path = find(item, "path")
                layer, width = layers[path[1]], float(path[2]) * scale
                pts = [(float(path[i]) * scale, -float(path[i + 1]) * scale) for i in range(3, len(path) - 1, 2)]
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6:
                        continue
                    k = (layer, pcbnew.FromMM(x0) // 1000, pcbnew.FromMM(y0) // 1000, pcbnew.FromMM(x1) // 1000, pcbnew.FromMM(y1) // 1000)
                    if k in have_seg:
                        continue
                    t = pcbnew.PCB_TRACK(b)
                    t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x0), pcbnew.FromMM(y0)))
                    t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
                    t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(layer); t.SetNet(ni)
                    b.Add(t); n_tr += 1
            elif item[0] == "via":
                vx, vy = float(item[2]) * scale, -float(item[3]) * scale
                if any(abs(vx - px) < 0.02 and abs(vy - py) < 0.02 for px, py in have_via_mm):
                    continue
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(float(item[2]) * scale), pcbnew.FromMM(-float(item[3]) * scale)))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(ni)
                b.Add(v); n_via += 1
    # GND pours on both layers (clipped to the board), then refill
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer); z.SetNet(b.FindNet("GND")); z.SetIsFilled(True)
        z.SetMinThickness(pcbnew.FromMM(0.2)); z.SetLocalClearance(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        ol = z.Outline(); ol.NewOutline()
        for x, y in ((0.3, -11.7), (117.7, -11.7), (117.7, 11.7), (0.3, 11.7)):
            ol.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    unrouted = b.GetConnectivity().GetUnconnectedCount(False)
    pcbnew.SaveBoard(dst, b)
    print("tracks", n_tr, "vias", n_via, "unconnected items:", unrouted)
    return unrouted


if __name__ == "__main__":
    sys.exit(1 if main(*sys.argv[1:4]) else 0)
