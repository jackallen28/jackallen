"""Autoroute with Freerouting (needs xvfb + java + the jar), then import the result and add GND pours.
python3 route.py placed.kicad_pcb routed.kicad_pcb     (about 3 minutes)
Then check it with tools/drc.py.  The checked-in routed board needed one extra via by hand (COL3 at 64.464, 2.103)."""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
src, dst = sys.argv[1], sys.argv[2]
jar = os.environ.get("FREEROUTING_JAR", "freerouting.jar")
work = os.path.dirname(os.path.abspath(dst))
dsn, ses = os.path.join(work, "_route.dsn"), os.path.join(work, "_route.ses")
sys.path.append("/usr/lib/python3/dist-packages")
import pcbnew
assert pcbnew.ExportSpecctraDSN(pcbnew.LoadBoard(src), dsn), "DSN export failed"
subprocess.run(["xvfb-run", "-a", "java", "-jar", jar, "-de", dsn, "-do", ses, "-mp", "40"], check=True, timeout=1500)
subprocess.run([sys.executable, os.path.join(here, "import_ses.py"), src, ses, dst], check=True)
