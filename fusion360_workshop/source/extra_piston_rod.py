"""04 EXTRA - Bare piston and connecting rod (9 components).

The same piston/rod sub-assembly used in the inline-4 engine, on its own.
Origin = centre of the big-end bore, rod along +Z, gudgeon pin along X.
"""
import sys
from cadlib import *
import advanced_inline4_engine as E


def build():
    P = dict(
        rod=Part("Connecting Rod", E.connecting_rod(), "steel"),
        cap=Part("Rod Cap", E.rod_cap(), "steel"),
        bolt=Part("Rod Bolt M9", E.rod_bolt(), "black_oxide"),
        piston=Part("Piston", E.piston(), "aluminium"),
        pin=Part("Gudgeon Pin", E.gudgeon_pin(), "brass"),
        ring=Part("Compression Ring", E.piston_ring(1.5), "dark_steel"),
        oil=Part("Oil Control Ring", E.oil_ring(), "blue"),
    )
    L = E.ROD_L
    root = Asm("Piston and Connecting Rod")
    root.add(P["rod"])
    root.add(P["cap"])
    for y in (-E.ROD_BOLT_Y, E.ROD_BOLT_Y):
        root.add(P["bolt"], place((0, y, -26), [("x", 180)]))
    root.add(P["piston"], place((0, 0, L)))
    root.add(P["pin"], place((0, 0, L), [("y", 90)]))
    root.add(P["ring"], place((0, 0, L + 24)))
    root.add(P["ring"], place((0, 0, L + 19.5), [("z", 120)]))
    root.add(P["oil"], place((0, 0, L + 13), [("z", 240)]))
    return root


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "04_Extra_Piston_and_Rod.step"
    root = build()
    check_assembly(root)
    print(export_step(root, out, "Extra: bare piston and connecting rod"))
