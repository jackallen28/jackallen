import cairosvg
import sys, math
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, "/home/user/jackallen/hardware/circuitpath-keychain/tools")
import pcbnew
import build_pcb as B, design as D

b = pcbnew.LoadBoard("/home/user/jackallen/hardware/circuitpath-keychain/kicad/circuitpath-keychain.kicad_pcb")
S = 16.0                       # px per mm
PADX, PADY = 6, 6
W, H = D.BODY_END, D.BODY_H
mm = pcbnew.ToMM

def outline_path(flip):
    pts = []
    for s in B.rounded_outline():
        if s[0] == "L":
            if s[1] != s[2]: pts += [s[1], s[2]]
        else:
            c, a, e = s[1], s[2], s[3]
            a0 = math.atan2(a[1]-c[1], a[0]-c[0]); b0 = math.atan2(e[1]-c[1], e[0]-c[0])
            d = (b0-a0+math.pi) % (2*math.pi) - math.pi
            r = math.hypot(a[0]-c[0], a[1]-c[1])
            pts += [(c[0]+r*math.cos(a0+d*k/12), c[1]+r*math.sin(a0+d*k/12)) for k in range(13)]
    return pts

def tx(x, flip): return ((W - x) if flip else x) + PADX
def ty(y): return y + H/2 + PADY

def build(flip, out):
    side = "B" if flip else "F"
    o = []
    vw, vh = (W + 2*PADX) * S, (H + 2*PADY) * S
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{vw}" height="{vh}" viewBox="0 0 {W+2*PADX} {H+2*PADY}">')
    o.append('<defs><radialGradient id="bg" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#3a3d45"/><stop offset="1" stop-color="#14151a"/></radialGradient>'
             '<linearGradient id="mask" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7a3fb0"/><stop offset="0.5" stop-color="#5f2d90"/><stop offset="1" stop-color="#4a2273"/></linearGradient>'
             '<linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f2f2f4"/><stop offset="0.5" stop-color="#b9bcc4"/><stop offset="1" stop-color="#8d9099"/></linearGradient>'
             '<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6dc8a"/><stop offset="1" stop-color="#c79a2c"/></linearGradient>'
             '<linearGradient id="black" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#34343a"/><stop offset="1" stop-color="#0d0d10"/></linearGradient>'
             '<radialGradient id="led" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="#d8f0ff"/><stop offset="0.45" stop-color="#3fa4ff"/><stop offset="1" stop-color="#1257c9"/></radialGradient>'
             '<radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#5cb8ff" stop-opacity="0.55"/><stop offset="1" stop-color="#5cb8ff" stop-opacity="0"/></radialGradient></defs>')
    o.append(f'<rect width="100%" height="100%" fill="url(#bg)"/>')
    pts = [(tx(x, flip), ty(y)) for x, y in outline_path(flip)]
    poly = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
    o.append(f'<polygon points="{poly}" transform="translate(0.5,0.8)" fill="#000" opacity="0.45"/>')
    hx, hy, hd = D.KEYRING_HOLE
    o.append(f'<defs><mask id="m"><rect width="100%" height="100%" fill="#fff"/><circle cx="{tx(hx,flip)}" cy="{ty(hy)}" r="{hd/2}" fill="#000"/></mask></defs>')
    o.append(f'<polygon points="{poly}" fill="url(#mask)" stroke="#2d1348" stroke-width="0.12" mask="url(#m)"/>')
    o.append(f'<circle cx="{tx(hx,flip)}" cy="{ty(hy)}" r="{hd/2+0.05}" fill="url(#bg)" stroke="#d9b24a" stroke-width="0.3"/>')

    def rect(x, y, w, h, fill, rx=0.05, extra=""):
        o.append(f'<rect x="{x-w/2:.3f}" y="{y-h/2:.3f}" width="{w:.3f}" height="{h:.3f}" rx="{rx}" fill="{fill}" {extra}/>')

    for fp in b.GetFootprints():
        ref = fp.GetReference()
        onbot = fp.IsFlipped()
        thru = ref in ("D3", "D4", "D5", "J2")
        if onbot != flip and not thru and ref != "J1":
            continue
        if ref == "J1" and flip:
            continue
        # pads
        bb = None
        for pad in fp.Pads():
            p = pad.GetPosition(); sz = pad.GetSize()
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH: continue
            x, y = tx(mm(p.x), flip), ty(mm(p.y))
            w, h = mm(sz.x), mm(sz.y)
            ang = pad.GetOrientationDegrees()
            if abs(ang % 180 - 90) < 1: w, h = h, w
            if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE: w = h = max(w, h)
            if ref in ("U1",) or fp.GetReference().startswith(("R", "C")) or ref.startswith("D") and ref not in ("D3","D4","D5") or ref in ("U2","U3","U4","Y1","SW1","SW2","J3") or ref == "J1" or ref=="J2":
                if onbot != flip and ref != "J1" and not thru: continue
                fill = "url(#gold)" if (ref in ("J1","J3") or thru) else "url(#metal)"
                if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                    o.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{w/2:.3f}" fill="url(#gold)"/>')
                else:
                    rect(x, y, w, h, fill, 0.08)
        c = fp.GetBoundingBox(False, False)
        cx, cy = tx(mm(c.GetCenter().x), flip), ty(mm(c.GetCenter().y))
        cw, ch = mm(c.GetWidth()), mm(c.GetHeight())
        x0, y0 = (D.MATRIX_X0, 0)
        if fp.GetFPIDAsString().startswith("LED_0603"):
            rect(cx, cy, 1.0, 0.8, "url(#black)", 0.1)
            o.append(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="1.5" fill="url(#glow)"/>')
            rect(cx, cy, 0.55, 0.55, "url(#led)", 0.1)
        elif ref.startswith("R") and fp.GetFPIDAsString().startswith("R_0603"):
            rect(cx, cy, 0.9, 0.8, "#16161a", 0.06)
        elif ref.startswith("C") and fp.GetFPIDAsString().startswith("C_0"):
            rect(cx, cy, cw - 1.0 if cw > 2 else 0.9, 0.85, "#a9793a", 0.06)
        elif ref == "U1":
            rect(cx, cy, 10.0, 10.0, "url(#black)", 0.2)
            o.append(f'<circle cx="{cx-3.9:.3f}" cy="{cy-3.9:.3f}" r="0.5" fill="#777"/>')
            o.append(f'<text x="{cx}" y="{cy-0.3}" fill="#c9c9d0" font-size="1.3" font-family="DejaVu Sans" text-anchor="middle">ATmega</text><text x="{cx}" y="{cy+1.3}" fill="#c9c9d0" font-size="1.3" font-family="DejaVu Sans" text-anchor="middle">32U4-AU</text>')
        elif ref in ("U2", "U3"):
            rect(cx, cy, 7.5, 15.4, "url(#black)", 0.3)
            o.append(f'<circle cx="{cx-2.6:.3f}" cy="{cy-6.6:.3f}" r="0.5" fill="#777"/>')
            o.append(f'<text x="{cx}" y="{cy+0.4}" fill="#c9c9d0" font-size="1.3" font-family="DejaVu Sans" text-anchor="middle" transform="rotate(-90 {cx} {cy})">MAX7219</text>')
        elif ref == "U4":
            rect(cx, cy, 1.6, 2.9, "url(#black)", 0.1)
        elif ref in ("D1", "D2"):
            rect(cx, cy, 1.6, 1.2, "url(#black)", 0.1); rect(cx-0.55, cy, 0.25, 1.2, "#bbb", 0)
        elif ref == "Y1":
            rect(cx, cy, 3.1, 2.4, "url(#metal)", 0.2)
            o.append(f'<text x="{cx}" y="{cy+0.4}" fill="#555" font-size="1" font-family="DejaVu Sans" text-anchor="middle">16.000</text>')
        elif ref in ("SW1", "SW2"):
            rect(cx, cy, 5.1, 5.1, "url(#metal)", 0.3)
            o.append(f'<circle cx="{cx}" cy="{cy}" r="1.9" fill="url(#black)" stroke="#222" stroke-width="0.1"/><circle cx="{cx-0.4}" cy="{cy-0.5}" r="0.6" fill="#fff" opacity="0.25"/>')
        elif ref == "J2":
            rect(cx, cy, 3.3, 9.0, "url(#metal)", 0.5)
            rect(cx, cy, 1.0, 7.0, "#0b0b0d", 0.5)
            rect(cx, cy, 0.3, 5.6, "#8d8d96", 0.1)
        elif ref in ("D3", "D4", "D5"):
            col = {"D3": ("#ff6a5a", "#c01810"), "D4": ("#ffc255", "#d98400"), "D5": ("#8ff08a", "#1fa21f")}[ref]
            gx, gy = tx(mm(fp.GetPosition().x) + 1.27, flip), ty(mm(fp.GetPosition().y))
            if flip: continue
            o.append(f'<circle cx="{gx:.3f}" cy="{gy:.3f}" r="3.1" fill="#000" opacity="0.25" transform="translate(0.3,0.4)"/>')
            o.append(f'<circle cx="{gx:.3f}" cy="{gy:.3f}" r="2.9" fill="{col[1]}"/><circle cx="{gx:.3f}" cy="{gy:.3f}" r="2.55" fill="{col[0]}" opacity="0.92"/>')
            o.append(f'<ellipse cx="{gx-0.8:.3f}" cy="{gy-0.9:.3f}" rx="1.0" ry="0.6" fill="#fff" opacity="0.55" transform="rotate(-35 {gx-0.8} {gy-0.9})"/>')

    # silkscreen text (white, as JLCPCB prints on purple)
    for t in b.GetDrawings():
        if t.GetClass() == "PCB_TEXT" and (t.GetLayer() == pcbnew.B_SilkS) == flip and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            p = t.GetPosition(); sz = mm(t.GetTextSize().x)
            x, y = tx(mm(p.x), flip), ty(mm(p.y)); ang = t.GetTextAngleDegrees()
            o.append(f'<text x="{x:.3f}" y="{y+sz*0.35:.3f}" fill="#f4f1fa" font-size="{sz*1.15:.2f}" font-family="DejaVu Sans" font-weight="bold" text-anchor="middle" transform="rotate({-ang if not flip else ang} {x:.3f} {y:.3f})">{t.GetText()}</text>')
    o.append("</svg>")
    open(out + ".svg", "w").write("\n".join(o))
    cairosvg.svg2png(url=out + ".svg", write_to=out + ".png", output_width=int(vw))

d = "docs/"
build(False, d + "keychain-top"); build(True, d + "keychain-back")
print("ok")
