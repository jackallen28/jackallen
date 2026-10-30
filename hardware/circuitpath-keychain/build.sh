#!/bin/sh
# Regenerates every file from tools/design.py. Needs KiCad 7+ (for pcbnew + kicad-cli) and `pip install kiutils`.
set -e
cd "$(dirname "$0")"
python3 tools/build_sch.py kicad/circuitpath-keychain.kicad_sch
python3 tools/build_pcb.py kicad/circuitpath-keychain.kicad_pcb      # placed, NOT routed
kicad-cli sch export netlist --format kicadxml -o /tmp/ck-net.xml kicad/circuitpath-keychain.kicad_sch
python3 tools/check_netlists.py /tmp/ck-net.xml kicad/circuitpath-keychain.kicad_pcb
python3 tools/export_fab.py kicad/circuitpath-keychain.kicad_pcb
