# jackallen

## VIBEDUINO — Allentronics Education Services

Hexagonal plug-in modules and an Arduino Uno R3 shield that holds four of them.
Every module is the same 1-inch hex with the same keyed 10-pin bus, so any module fits in
any slot.

* [`hardware/`](hardware/README.md): system spec, bus pinout, slot map and design notes
* `hardware/kicad/`: KiCad projects, PCB + schematic (shield + 10 modules), and the custom library
* [`hardware/BOM.md`](hardware/BOM.md), `hardware/fab/`: BOM with manufacturer and LCSC part
  numbers, Gerbers, drill and pick-and-place files
* [`hardware/panel/`](hardware/panel/README.md): all ten modules on one JLCPCB production panel,
  with order settings
* `hardware/3d/`: STEP models of every board and of the full Uno + shield + modules stack
* `hardware/schematics/`: all schematics in one PDF
* `hardware/generator/`: Python generator that builds, routes and checks every board
* `hardware/previews/`: rendered previews

[www.allentronics.com.au](https://www.allentronics.com.au)
