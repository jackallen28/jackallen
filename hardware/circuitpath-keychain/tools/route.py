"""Autoroute with Freerouting, then add the GND pours.  python3 route.py in.kicad_pcb out.kicad_pcb"""
import os, subprocess, sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
src, dst = sys.argv[1], sys.argv[2]
jar = os.environ.get("FREEROUTING_JAR", "/tmp/claude-0/-home-user/d2981c74-f7ff-582a-a4c3-8a74899fe80e/scratchpad/fr/fr.jar")
work = os.path.dirname(os.path.abspath(dst))
dsn, ses = os.path.join(work, "_route.dsn"), os.path.join(work, "_route.ses")
b = pcbnew.LoadBoard(src)
assert pcbnew.ExportSpecctraDSN(b, dsn), "DSN export failed"
subprocess.run(["java", "-Djava.awt.headless=true", "-jar", jar, "-de", dsn, "-do", ses, "-mp", "40"], check=True, timeout=1500)
b = pcbnew.LoadBoard(src)
assert pcbnew.ImportSpecctraSES(b, ses), "SES import failed"
# GND pours on both layers, clipped to the outline
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(b.FindNet("GND"))
    z.SetIsFilled(True)
    z.SetMinThickness(pcbnew.FromMM(0.2))
    z.SetLocalClearance(pcbnew.FromMM(0.2))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((-1, -13), (130, -13), (130, 13), (-1, 13)):
        ol.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
