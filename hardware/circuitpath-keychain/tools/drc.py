"""Run KiCad's DRC with JLCPCB-like limits and print a summary.  python3 drc.py board.kicad_pcb [report.rpt]
Returns non-zero if there are unconnected items or errors (silkscreen warnings and missing-library notes are ignored)."""
import re, sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
ds = b.GetDesignSettings()
mm = pcbnew.FromMM
ds.m_MinClearance = mm(0.15); ds.m_TrackMinWidth = mm(0.15); ds.m_ViasMinSize = mm(0.5); ds.m_MinThroughDrill = mm(0.3)
ds.m_CopperEdgeClearance = mm(0.3); ds.m_HoleClearance = mm(0.2); ds.m_HoleToHoleMin = mm(0.25)
ds.m_SolderMaskMinWidth = mm(0.1); ds.m_MinSilkTextHeight = mm(0.8)
rpt = sys.argv[2] if len(sys.argv) > 2 else "/tmp/drc.rpt"
pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
bad = 0
for blk in re.split(r"\n(?=\[)", open(rpt).read()):
    m = re.match(r"\[(\w+)\]", blk)
    if not m or m.group(1) in ("lib_footprint_issues", "silk_overlap", "silk_edge_clearance", "silk_over_copper", "text_height"):
        continue
    bad += 1
    print(re.sub(r"\s+", " ", blk)[:260])
print("serious DRC items:", bad)
sys.exit(1 if bad else 0)
