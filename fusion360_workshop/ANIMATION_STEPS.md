# Animation Steps – Quick Guide

**Setup (all files):** Upload the STEP file to Fusion 360 and open it. Switch the workspace to **ANIMATION**. All directions below use the model's own axes: Z is up. Distances are approximate, so anything that clearly separates the parts is fine.

**Core tools:**
- **Transform Components** moves or rotates parts. Use **Set Pivot** and click a round edge to rotate about its centre.
- **Auto Explode** spreads everything out automatically.
- **Restore Home** puts everything back.
- Each action starts at the **playhead** on the timeline. Drag the action bars to change timing.

---

## 00 Starter – Jar with Lid (3 parts)
1. **Lid** – rotate 2 turns (720°) about Z and move up 10 mm in the same action to unscrew it.
2. **Lid**: move up 70 mm.
3. **Lid Seal**: move up 40 mm.
4. **Restore Home** to screw it back on.

*Learn:* move vs rotate, Set Pivot, the timeline.

## 01 Simple – Spur Gear Reduction (17 parts)
1. **Gears in mesh**: rotate *Pinion + Input Shaft* +360° and *Driven Gear + Output Shaft* −180° over the **same** 4 s. The teeth should stay meshed, showing a 2:1 ratio and opposite rotation.
2. **New storyboard, teardown**:
   1. Shaft collars ±Y 100.
   2. Shafts slide out ±Y 130.
   3. Both gears up 150.
   4. Bearings ±Y 45.
   5. Cap screws down 45.
   6. Brackets up 80.

*Learn:* simultaneous actions, rotation ratios, a logical disassembly order.

## 02 Moderate – Game Controller (22 parts, 2 sub-assemblies)
1. **Screws (×5)**: move down 40 mm from the underside.
2. **Front Shell Assembly**: move up 90 mm. The buttons and D-pad go with it because they belong to this sub-assembly.
3. Inside the front shell assembly, push the **D-pad and buttons A/B/X/Y** up 30 mm.
4. **Main Board Assembly** (PCB with thumbsticks): move up 45 mm. Then lift the **Thumbstick Caps** up a further 30 mm.
5. **Battery** up 15 mm, **Rumble Motors** up 25 mm.
6. **Triggers**: rotate about 30° about their pivot pin (X axis), then slide them back 40 mm (+Y).

*Try:* compare **Auto Explode: One Level** with **All Levels** to see how sub-assemblies behave.
*Learn:* sub-assemblies, selecting inside a sub-assembly in the Browser.

## 03 Advanced – Inline-4 Engine (141 parts, nested)
**Storyboard 1, teardown** (hide removed parts with the eye icon to keep the view clear):
1. Drain plug down, then the ignition coils and oil filler cap up.
2. Valve cover up, then the spark plugs up.
3. Crank pulley bolt and crank pulley off, then the timing belt forward (−X).
4. Intake manifold −Y, exhaust manifold +Y, oil filter −Y (rotate it as well to unscrew).
5. Head bolts up, then the **Cylinder Head Assembly** up, then the head gasket up.
6. Oil pan down.
7. **Rod caps and bolts** down, then each **Piston and Rod Assembly** up out of the bores.
8. Main cap bolts and main caps down, then the **Crankshaft Assembly** down.

**Storyboard 2, timing**: hide the block, head and covers. Rotate the **Crankshaft Assembly** 720° about X while the **Camshaft + Cam Pulley** rotate 360° over the same 8 s. This shows the 2:1 crank-to-cam ratio.

*Discuss:* the pistons don't follow the crank, because Animation ignores joints. Motion Study in the Design workspace can show linked motion.

## 04 Extra – Piston and Connecting Rod (9 parts)
1. **Rod Bolts** down 120 mm.
2. **Rod Cap** down 70 mm.
3. **Gudgeon Pin** slides out sideways 90 mm (Y).
4. **Piston** up 90 mm.
5. **Oil ring, then the compression rings**, up off the piston one at a time (110–150 mm).

*Learn:* a quick exploded view, plus a callout naming each part.

---
**Finish every file** by adding a **Callout** or two, then **Publish Video**.
