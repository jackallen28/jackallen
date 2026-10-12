"""Board layout, routing and outputs for the standalone ATmega328P board (see gen_atmega.py).

Uses the board tools of the Nano carrier boards (../../hardware/tools/gen_pcb.py): footprints from
the schematic's netlist, fixed wide tracks for the valve current, Freerouting for the rest, GND
pours on both layers with stitching vias, KiCad's design-rule check and the gerber export.

Coordinates are in mm from the board's top-left corner, y down. A placement is
    ref: (x, y, rotation)          footprint origin (the middle of SMD parts)
    ref: (x, y, rotation, 'tl')    top-left corner of the part's courtyard
"""
import argparse
import csv
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import gen_atmega as ga  # noqa: E402  (also puts ../../hardware/tools on the path)
import gen_pcb as gp  # noqa: E402
import pcbnew  # noqa: E402

W, H = 57.0, 56.0
P = gp.P
F = gp.F

# Net classes for this board. The valve current path is laid as fixed 2.5 mm tracks (PREROUTE);
# what Freerouting adds on these nets only feeds the regulator, gate resistors and decoupling.
gp.NETCLASSES = {
    'Power12V': (1.0, 0.3, 0.8, 0.4, ['+12V', '/12V_IN', '/12V_FUSED', '/12V_SW', '/SOL_OUT']),
    'Power5V': (0.5, 0.2, 0.6, 0.3, ['+5V', '/VBUS']),
    'Ground': (0.5, 0.2, 0.6, 0.3, ['GND']),
    'Switcher': (0.6, 0.25, 0.6, 0.3, ['/SW']),
}
gp.VARIANTS['atmega'] = dict(dir=ga.PROJ_DIR, project=ga.PROJECT)

_L = dict(size=0.8)
_V = dict(size=0.8, rot=90)

LAYOUT = dict(
    size=(W, H),
    place={
        'H1': (4.8, 4.8, 0), 'H2': (50.2, 4.8, 0), 'H3': (4.8, 51.2, 0), 'H4': (50.2, 51.2, 0),
        # top edge: ESP link (left), valve / flow terminal (right)
        'J4': (9.8, 0.6, 0, 'tl'), 'J3': (23.6, 0.3, 180, 'tl'),
        'R11': (12.4, 9.3, 0), 'R12': (16.2, 9.3, 0), 'R21': (20.0, 9.3, 0),
        # flow sensor input under J3
        'R1': (27.4, 14.4, 90), 'R2': (25.6, 14.4, 90), 'C16': (31.7, 14.4, 90), 'C17': (28.4, 19.6, 0),
        # valve switch Q1 under J3's valve pin, flyback diode D2 across J3 pins 1-2
        'Q1': (38.6, 16.4, 90), 'D2': (43.4, 16.4, 270),
        'Q2': (32.6, 18.4, 0), 'R18': (34.4, 21.3, 0), 'R19': (29.8, 16.4, 90), 'R20': (33.6, 14.6, 90),
        # ATmega328P in the middle, LED pins towards the panel connectors on the left
        'U4': (21.0, 25.0, 270), 'Y1': (18.4, 17.8, 0), 'C10': (14.8, 18.6, 90), 'C11': (13.0, 18.6, 90),
        'C12': (21.4, 17.9, 90), 'C13': (23.2, 17.9, 90), 'C14': (19.0, 32.0, 90), 'C15': (20.8, 32.0, 90),
        'R39': (28.2, 24.6, 0), 'D4': (29.4, 33.6, 0), 'C9': (28.2, 22.8, 0),
        'R37': (29.0, 29.8, 0), 'R38': (29.0, 31.6, 0), 'R40': (22.6, 32.0, 90), 'D5': (24.4, 32.0, 90),
        'J10': (8.2, 28.2, 0, 'tl'),
        # panel connectors on the left edge, with the button and LED resistors
        'J5': (0.3, 9.8, 90, 'tl'), 'J6': (0.3, 18.6, 90, 'tl'), 'J7': (0.3, 27.4, 90, 'tl'),
        'J8': (0.3, 36.2, 90, 'tl'),
        'R3': (9.6, 12.6, 90), 'C18': (11.4, 12.6, 90),
        'R4': (12.4, 22.4, 0), 'R5': (12.4, 24.2, 0), 'R6': (12.4, 26.0, 0),
        # USB-C and USB-serial on the right
        'J9': (45.6, 10.0, 90, 'tl'), 'U3': (35.6, 25.5, 180), 'C7': (30.8, 23.4, 90), 'C8': (30.3, 27.6, 180),
        'R35': (47.3, 22.0, 0), 'R36': (47.3, 23.8, 0), 'D3': (47.95, 26.0, 0),
        # 433 MHz receiver socket on the right edge, its filter and input resistors beside it
        'U2': (51.2, 21.6, 0, 'tl'),
        'R17': (47.3, 28.4, 0), 'C19': (47.3, 30.4, 0), 'C20': (47.3, 32.4, 0),
        'R7': (47.3, 34.2, 0), 'R8': (47.3, 36.0, 0), 'R9': (47.3, 37.8, 0), 'R10': (47.3, 39.6, 0),
        'R13': (46.4, 42.2, 270), 'R14': (48.2, 42.2, 270), 'R15': (50.0, 42.2, 270), 'R16': (51.8, 42.2, 270),
        # power: terminals and resettable fuse on the bottom edge, reverse-polarity MOSFET, 5 V buck
        'J1': (9.8, 45.0, 0, 'tl'), 'F1': (21.3, 45.6, 90, 'tl'), 'J2': (27.6, 45.0, 0, 'tl'),
        'Q3': (39.5, 40.2, 270), 'R30': (34.8, 39.4, 90), 'C1': (12.9, 40.5, 0),
        'U1': (23.0, 40.6, 180), 'C2': (25.2, 35.2, 0), 'C3': (25.0, 37.3, 0), 'C4': (23.0, 43.6, 0),
        'L1': (28.2, 40.6, 0), 'C5': (32.0, 38.6, 90), 'C6': (32.0, 42.0, 90),
        'R31': (18.4, 42.2, 90), 'R32': (20.2, 42.2, 90), 'R33': (20.2, 38.6, 90), 'R34': (18.4, 38.6, 90),
    },
    texts=[
        # J3, valve and flow sensor terminal (pin 1 at the right)
        ('VALVE+', 41.88, 11.9, _L), ('GND', 36.8, 11.9, _L), ('+5V', 31.72, 11.9, _L), ('FLOW', 26.64, 11.9, _L),
        ('5V GND RX TX', 16.45, 8.0, _L),
        ('12V+', 12.84, 44.6, _L), ('GND', 17.92, 44.6, _L), ('SW IN', 30.64, 44.6, _L),
        ('SW OUT', 35.72, 44.6, _L), ('LAMP-', 40.8, 44.6, _L),
        ('GND', 49.6, 22.6, _V), ('ANT', 49.6, 38.0, _V),
        ('J5 BUTTON', 7.62, 14.0, _V), ('J6 25L', 7.62, 22.8, _V), ('J7 50L', 7.62, 31.6, _V),
        ('J8 100L', 7.62, 40.4, _V),
        ('WATER VALVE CONTROLLER', 27.5, 26.0, dict(size=1.2, bottom=True)),
        ('ATMEGA328P  rev A1', 27.5, 28.2, dict(size=1.0, bottom=True)),
    ],
    labelled=('J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8'),
    refs={'R11': (9.9, 9.3, 0)},
    # fixed 2.5 mm tracks for the valve current: (net, width, layer, points); a point is (x, y)
    # or 'REF.PAD' for the middle of that pad ('REF.6+7': midway between pads 6 and 7)
    preroute=[
        ('/12V_IN', 2.5, 'F.Cu', ['J1.1', (12.84, 53.6), (21.6, 53.6), 'F1.1']),
        ('/12V_FUSED', 2.5, 'F.Cu', ['F1.2', (27.0, 46.81), (30.64, 46.81), 'J2.1']),
        ('/12V_SW', 2.5, 'F.Cu', ['J2.2', (35.72, 46.0), 'Q3.6+7']),
        ('+12V', 2.5, 'F.Cu', ['Q3.2', (40.14, 36.4), (44.1, 36.4), (44.1, 21.5), (37.96, 21.5), 'Q1.2']),
        ('/SOL_OUT', 2.5, 'F.Cu', ['Q1.6+7', (41.88, 10.64), 'J3.1']),
        ('/SOL_OUT', 2.5, 'F.Cu', [(41.88, 10.64), (43.4, 12.16), 'D2.1']),
        # bars joining all the drain pins and all the source pins of each MOSFET
        ('/SOL_OUT', 1.0, 'F.Cu', ['Q1.8', 'Q1.5']), ('+12V', 1.0, 'F.Cu', ['Q1.1', 'Q1.3']),
        ('/12V_SW', 1.0, 'F.Cu', ['Q3.5', 'Q3.8']), ('+12V', 1.0, 'F.Cu', ['Q3.1', 'Q3.3']),
        # the USB-C socket's two VBUS pads, joined on the back under its signal pads
        ('/VBUS', 0.5, 'F.Cu', ['J9.A9', (45.3, 12.87)]), ('/VBUS', 0.5, 'B.Cu', [(45.3, 12.87), (45.3, 17.77)]),
        ('/VBUS', 0.5, 'F.Cu', [(45.3, 17.77), 'J9.A4']),
    ],
    vias=[('/VBUS', (45.3, 12.87)), ('/VBUS', (45.3, 17.77))],
)


def widen(lay, dx, from_x=7.5):
    """Moves everything right of the panel connectors (x >= from_x) right by dx, to open a lane
    for vertical tracks beside them. The connector labels in the lane move by half as much."""
    sx = lambda x: x + dx if x >= from_x else x  # noqa: E731
    lay['place'] = {r: (sx(v[0]),) + tuple(v[1:]) for r, v in lay['place'].items()}
    lay['texts'] = [(t[0], t[1] + (dx / 2 if t[0].startswith('J') and abs(t[1] - 7.62) < 0.01 else
                                   (dx if t[1] >= from_x else 0)), *t[2:]) for t in lay['texts']]
    lay['preroute'] = [(n, w, l, [p if isinstance(p, str) else (sx(p[0]), p[1]) for p in pts])
                       for n, w, l, pts in lay['preroute']]
    lay['vias'] = [(n, (sx(x), y)) for n, (x, y) in lay.get('vias', ())]
    lay['refs'] = {r: (sx(x), y, a) for r, (x, y, a) in lay.get('refs', {}).items()}


widen(LAYOUT, W - 55.0)


def pad_xy(board, spec):
    if isinstance(spec, tuple):
        return spec
    ref, nums = spec.split('.')
    fp = board.FindFootprintByReference(ref)
    pads = [p for p in fp.Pads() if p.GetNumber() in nums.split('+')]
    xs = [p.GetPosition().x for p in pads]
    ys = [p.GetPosition().y for p in pads]
    return (pcbnew.ToMM(sum(xs) / len(xs)) - gp.OX, pcbnew.ToMM(sum(ys) / len(ys)) - gp.OY)


def preroute(board, routes, vias=()):
    for net, (x, y) in vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(x, y))
        v.SetWidth(F(0.6))
        v.SetDrill(F(0.3))
        v.SetNet(board.FindNet(net))
        v.SetLocked(True)
        board.Add(v)
    for net, width, layer, pts in routes:
        pts = [pad_xy(board, p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*a))
            t.SetEnd(P(*b))
            t.SetWidth(F(width))
            t.SetLayer(board.GetLayerID(layer))
            t.SetNet(board.FindNet(net))
            t.SetLocked(True)
            board.Add(t)


def build(jar, passes, work, place_only):
    lay = LAYOUT
    sch = os.path.join(ga.PROJ_DIR, ga.PROJECT + '.kicad_sch')
    pcb = os.path.join(ga.PROJ_DIR, ga.PROJECT + '.kicad_pcb')
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(ga.PROJ_DIR, ga.PROJECT + '.kicad_dru'), 'w') as f:
        f.write('(version 1)\n(rule "One thermal spoke is enough: every GND pad also has a routed track"\n'
                '  (constraint min_resolved_spokes 1))\n')
    comps, nets = gp.read_netlist(sch)
    board = gp.new_board(pcb)
    gp.add_nets(board, nets)
    gp.add_footprints(board, comps, nets, lay['place'], ga.PROJECT)
    gp.outline(board, W, H, 1.0)
    # a 0.5 mm strip along the edges with no tracks or vias, so the autorouter keeps its distance
    e = 0.5
    for x1, y1, x2, y2 in ((0, 0, W, e), (0, H - e, W, H), (0, 0, e, H), (W - e, 0, W, H)):
        z = gp.poly_zone(board, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], [pcbnew.F_Cu, pcbnew.B_Cu])
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetDoNotAllowCopperPour(False)
        z.SetZoneName('EDGE')
    for t in lay['texts']:
        gp.text(board, *t[:3], **(t[3] if len(t) > 3 else {}))
    hidden = gp.place_refs(board, W, H, [], lay['labelled'], lay.get('refs'))
    if hidden:
        print('no room on the silkscreen for:', ', '.join(hidden))
    preroute(board, lay['preroute'], lay.get('vias', ()))
    if not place_only:
        gp.autoroute(board, work, jar, passes)
        gp.gnd_pours(board, W, H)
        gp.fill(board)
        print('stitching vias:', gp.stitch(board, W, H))
        gp.fill(board)
    pcbnew.SaveBoard(pcb, board)
    gp.write_project_rules(os.path.join(ga.PROJ_DIR, ga.PROJECT + '.kicad_pro'))
    board = pcbnew.LoadBoard(pcb)
    viol, unc, errors, warnings, rep = gp.drc(board, os.path.join(work, 'drc.rpt'))
    print(f'atmega: {W:g} x {H:g} mm = {W * H:.0f} mm2; DRC {viol} violations ({errors} errors, '
          f'{warnings} warnings), {unc} unconnected; report {work}/drc.rpt')
    if not place_only:
        print('gerbers:', gp.exports(pcb, ga.PROJ_DIR, ga.PROJECT))


def main(cmd, argv):
    ap = argparse.ArgumentParser(prog='gen_atmega.py ' + cmd)
    ap.add_argument('--jar', default=os.environ.get('FREEROUTING_JAR', ''))
    ap.add_argument('--passes', type=int, default=100)
    ap.add_argument('--work', default=tempfile.mkdtemp(prefix='wvc-atmega-'))
    ap.add_argument('--place-only', action='store_true')
    a = ap.parse_args(argv)
    if cmd == 'pcb':
        if not a.place_only and not a.jar:
            raise SystemExit('give the Freerouting jar with --jar or $FREEROUTING_JAR')
        build(a.jar, a.passes, a.work, a.place_only)
    elif cmd == 'outputs':
        outputs()
    else:
        raise SystemExit(f'unknown command {cmd}')


# ---------------------------------------------------------------------------------------------
# Outputs: schematic PDF/SVG, BOMs, JLCPCB files, images, KiCad zip
# ---------------------------------------------------------------------------------------------
def comment(p):
    """Comment column text for JLCPCB: the value plus what identifies the part."""
    fp, v = p['fp'].split(':')[-1], p['value']
    if fp.startswith('R_0603'):
        return f'{v}{"R" if v.isdigit() else ""} 1% 0603'
    if fp.startswith('C_0603'):
        return f'{v} {"50V C0G" if v.endswith("pF") else "50V X7R"} 0603'
    if fp.startswith('C_0805'):
        return f'{v} {"25V X5R" if v == "10uF" else "X5R"} 0805'
    known = jlc_comment(v, fp)
    if known:
        return known
    return {'16MHz': '16 MHz crystal 3225, 20 pF', '10uH': '10 uH power inductor 4 x 4 x 2 mm',
            'green': 'LED green 0603', '100uF 25V': '100uF 25V electrolytic SMD 6.3 x 7.7 mm',
            '3A PTC': 'Resettable fuse 3 A hold, 30 V, 2920', 'USB-C': 'USB-C socket 16P (HRO TYPE-C-31-M-12)',
            'AO4407A': 'AO4407A P-MOSFET'}.get(v, v)


def jlc_comment(value, fp):
    import jlc_parts
    return jlc_parts.PARTS.get((value, fp), ('', ''))[0]


def outputs():
    import make_jlc
    import render_pcb
    d, name = ga.PROJ_DIR, ga.PROJECT
    sch, pcb = os.path.join(d, name + '.kicad_sch'), os.path.join(d, name + '.kicad_pcb')
    run = lambda *a: subprocess.run(a, check=True, capture_output=True)  # noqa: E731
    run('kicad-cli', 'sch', 'export', 'pdf', '-o', os.path.join(d, name + '-schematic.pdf'), sch)
    tmp = tempfile.mkdtemp()
    run('kicad-cli', 'sch', 'export', 'svg', '-o', tmp, sch)
    shutil.move(os.path.join(tmp, name + '.svg'), os.path.join(d, name + '-schematic.svg'))
    shutil.rmtree(tmp)
    run('kicad-cli', 'sch', 'export', 'netlist', '-o', os.path.join(d, name + '.net'), sch)
    # assembly drawing: every part's outline and reference (F.Fab), for the parts without room
    # for a silkscreen label
    run('kicad-cli', 'pcb', 'export', 'pdf', '--layers', 'F.Fab,Edge.Cuts', '-o',
        os.path.join(d, name + '-assembly.pdf'), pcb)

    board = pcbnew.LoadBoard(pcb)
    out = os.path.join(d, 'JLCPCB')
    os.makedirs(out, exist_ok=True)
    groups, cpl, smd, tht = {}, [], 0, 0
    for fp in sorted(board.GetFootprints(), key=lambda f: make_jlc.refkey(f.GetReference())):
        ref = fp.GetReference()
        p = ga.PARTS.get(ref)
        if ref.startswith('H') or not p or not p['in_bom']:
            continue
        lib_name = fp.GetFPID().GetLibItemName().wx_str()
        c, lcsc = comment(p), p['lcsc'].rstrip('*')
        g = groups.setdefault((c, lcsc), [lib_name, []])
        g[1].append(ref)
        smd += bool(fp.GetAttributes() & pcbnew.FP_SMD)
        tht += not (fp.GetAttributes() & pcbnew.FP_SMD)
        rot = fp.GetOrientationDegrees()
        for pattern, offset in make_jlc.ROTATION_OFFSET:
            if re.search(pattern, lib_name):
                rot += offset
        m = make_jlc.mid(fp)
        cpl.append([ref, f'{pcbnew.ToMM(m.x):.4f}', f'{-pcbnew.ToMM(m.y):.4f}', f'{rot % 360:g}',
                    'bottom' if fp.IsFlipped() else 'top'])
    rows = sorted(([c, ','.join(refs), make_jlc.package(n), lcsc] for (c, lcsc), (n, refs) in groups.items()),
                  key=lambda r: make_jlc.refkey(r[1].split(',')[0]))
    make_jlc.write_bom(os.path.join(out, f'{name}-BOM-JLCPCB'), rows)
    with open(os.path.join(out, f'{name}-CPL-JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        w.writerows(cpl)
    write_jlc_readme(out, name, rows, smd, tht)

    # full parts list, including what is not on the JLCPCB order
    with open(os.path.join(d, name + '-BOM.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['References', 'Qty', 'Value', 'Description', 'Footprint', 'JLCPCB / LCSC'])
        by = {}
        for ref, p in ga.PARTS.items():
            if p['sym'] is None:
                continue
            by.setdefault((p['value'], p['fp'], p['desc'] if p['value'] not in ('100nF', '10k', '1k') else '',
                           p['lcsc'].rstrip('*')), []).append(ref)
        for (v, fpid, desc, lcsc), refs in sorted(by.items(), key=lambda kv: make_jlc.refkey(kv[1][0])):
            refs = sorted(refs, key=make_jlc.refkey)
            if not desc:
                desc = {'100nF': 'Ceramic 100 nF decoupling / filter', '10k': 'Pull-up / pull-down',
                        '1k': 'Series resistor'}[v]
            w.writerow([', '.join(refs), len(refs), v, desc, fpid.split(':')[-1], lcsc])
        w.writerow(['(J10)', 1, '2 x 3 pin header 2.54 mm', 'ICSP, only while burning the bootloader', '', ''])
        w.writerow(['(J4)', 1, 'JST-XH 4-pin housing + crimped lead', 'ESP32 link lead', '', ''])
        w.writerow(['(J5-J8)', 4, 'JST-XH 2-pin housing + crimped lead', 'Panel button and LED leads', '', ''])
        w.writerow(['(H1-H4)', 4, 'M4 bolt + nut or standoff', 'Mounting', '', ''])

    os.makedirs(os.path.join(d, 'images'), exist_ok=True)
    prefix = os.path.join(d, 'images', 'atmega')
    render_pcb.render(pcb, prefix, 14)
    for svg in glob.glob(prefix + '-*.svg'):
        os.remove(svg)

    with zipfile.ZipFile(os.path.join(d, name + '-KiCad.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        for fn in (name + '.kicad_pro', name + '.kicad_sch', name + '.kicad_pcb', name + '.kicad_dru',
                   'WaterValve.kicad_sym', 'sym-lib-table'):
            z.write(os.path.join(d, fn), f'{name}/{fn}')
    print(f'{out}: {len(rows)} BOM lines, {len(cpl)} placements ({smd} SMD, {tht} through-hole)')


def write_jlc_readme(out, name, rows, smd, tht):
    lines = [
        '# JLCPCB order files: standalone ATmega328P board',
        '',
        'Upload these three files on jlcpcb.com:',
        '',
        f'1. **`{name}-gerbers.zip`**: the PCB. Options: 2 layers, 1.6 mm, 1 oz copper (the defaults).',
        f'2. **`{name}-BOM-JLCPCB.csv`** (or the same list as `.xlsx`, laid out like JLCPCB\'s sample BOM).',
        f'3. **`{name}-CPL-JLCPCB.csv`**: Designator, Mid X, Mid Y, Rotation, Layer (mm).',
        '',
        f'Turn on **PCB Assembly**, top side. All {smd + tht} parts are on the top: {smd} SMD and {tht} '
        'through-hole (terminals, JST headers, receiver socket). JLCPCB machine-places the SMD parts; the '
        'through-hole ones cost extra per joint, so you can untick them and solder them yourself.',
        '',
        '## Check in the placement preview',
        '',
        '- **U4 (ATmega328P) and U3 (CH340N):** the pin-1 dot matches the silkscreen dot.',
        '- **Q1, Q3 (AO4407A) and U1 (TPS54202H):** pin 1 matches the silkscreen mark.',
        '- **D2, D3, D4:** the cathode band at the end with the silkscreen bar.',
        '- **C1:** the + side at the + mark. **D5:** the green LED\'s cathode at the bar.',
        '',
        'The CPL already has the usual corrections for JLCPCB\'s reels (SOIC/SOP and TQFP +270, SOT-23 and '
        'SMD electrolytics +180), the same ones the KiCad JLCPCB plugins apply.',
        '',
        '## Not on the JLCPCB order',
        '',
        '- **J10 ICSP:** the 6 holes take a 2 x 3 pin header, needed only once to burn the bootloader (see '
        'the board README).',
        '- **Off-board parts:** valve, flow sensor, rocker switch, panel button and LEDs, JST housings and '
        'leads, the receiver and ESP32 modules, M4 bolts.',
        '',
        '## Part numbers',
        '',
        '| Designator | Part | JLCPCB / LCSC |',
        '|---|---|---|',
    ]
    for c, refs, _pkg, lcsc in rows:
        lines.append(f'| {refs.replace(",", ", ")} | {c} | {lcsc or "(choose)"} |')
    lines += [
        '',
        'The resistor and capacitor numbers, the crystal, the diodes and the LED come from JLCPCB\'s '
        'basic-parts list; JLCPCB\'s BOM step shows each matched part\'s value, so check them there. '
        'Stock changes daily: if a part is out of stock, the BOM step offers alternatives.',
        '',
    ]
    with open(os.path.join(out, 'README.md'), 'w') as f:
        f.write('\n'.join(lines))
