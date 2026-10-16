# Fusion 360 Animation Workshop – Example Assemblies

Five STEP assemblies (mostly car-themed) for practising the Fusion 360 **Animation** workspace.

| File | Level | Contents |
|---|---|---|
| `00_Starter_Jar_With_Lid.step` | Starter | Jar, screw lid and lid seal – 3 components |
| `01_Simple_Gear_Reduction.step` | Simple | 18T/36T spur gear reduction stage – 17 components |
| `02_Moderate_Wheel_Brake_Corner.step` | Moderate | Front wheel corner: knuckle, hub, vented disc, 4-piston caliper, alloy wheel and tyre – 30 components, 2 sub-assemblies |
| `03_Advanced_Inline4_Engine.step` | Advanced | Inline-4 SOHC 8-valve engine – 141 components, nested sub-assemblies |
| `04_Extra_Piston_and_Rod.step` | Extra | Bare piston and connecting rod (same as in the engine) – 9 components |

All models are in millimetres and built **Z-up**. Upload each one to Fusion 360 through the Data Panel (Upload) or File > Open > Open from my computer. Every part comes in as a named component.

`source/` contains the CadQuery scripts that generate the models (`python simple_gear_reduction.py` etc., requires `pip install cadquery`).
