"""JLCPCB / LCSC part numbers for both Nano boards, used by gen_schematic.py (the "LCSC Part #"
field on each symbol), gen_pcb.py (the same property on each footprint, which KiCad's JLCPCB
Fabrication Toolkit reads) and make_jlc.py (the BOM and CPL files).
"""

# (value, footprint) -> (comment for JLCPCB, LCSC/JLCPCB part number). An empty part number
# means none was confirmed: pick one in JLCPCB's BOM step, or leave the part off and solder it.
PARTS = {
    # ---- parts on both boards ----
    ('470uF 25V', 'CP_Radial_D10.0mm_P5.00mm'): ('470uF 25V electrolytic, 10 x 12.5 mm', 'C368591'),
    ('100uF 16V', 'CP_Radial_D6.3mm_P2.50mm'): ('100uF 16V electrolytic, 6.3 x 11 mm', 'C911212'),
    ('47uF 16V', 'CP_Radial_D5.0mm_P2.00mm'): ('47uF 16V electrolytic, 5 x 11 mm', 'C134586'),
    ('3A blade (ATO)', 'Fuseholder_Blade_ATO_Keystone_3557-2'): ('Keystone 3557-2 ATO blade fuse holder',
                                                                 'C352820'),
    ('12V DC IN', 'TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'):
        ('Screw terminal 2P 5.08 mm (KF128L-5.08-2P)', 'C474940'),
    ('MAIN SWITCH', 'TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal'):
        ('Screw terminal 3P 5.08 mm (KF128L-5.08-3P)', 'C474941'),
    ('VALVE / FLOW', 'TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal'):
        ('Screw terminal 4P 5.08 mm (DB128L-5.08-4P)', 'C2827883'),
    ('ESP32', 'JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'): ('JST XH 4-pin header B4B-XH-A', 'C144395'),
    ('BUTTON', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('LED 25L', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('LED 50L', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('LED 100L', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('R-78E5.0-1.0 or L7805', 'TO-220-3_Vertical'): ('RECOM R-78E5.0-1.0 5 V switching regulator',
                                                    'C3033024'),
    ('RX480E-4', 'PinSocket_1x07_P2.54mm_Vertical'): ('7-pin female header 2.54 mm (receiver socket)',
                                                      'C6684533'),
    # ---- mixed SMD + THT board ----
    ('100nF', 'C_0805_2012Metric_Pad1.18x1.45mm_HandSolder'): ('100nF 50V X7R 0805', 'C49678'),
    ('10nF', 'C_0805_2012Metric_Pad1.18x1.45mm_HandSolder'): ('10nF 50V X7R 0805', 'C1710'),
    ('S3M', 'D_SMC'): ('S3M 3A 1000V diode', 'C388240'),
    ('IRFR5305', 'TO-252-2'): ('IRFR5305 P-MOSFET', 'C2624'),
    ('2N7002', 'SOT-23'): ('2N7002 N-MOSFET', 'C8545'),
    ('10k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('10k 1% 0805', 'C17414'),
    ('1k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('1k 1% 0805', 'C17513'),
    ('100k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('100k 1% 0805', 'C149504'),
    ('330', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('330R 1% 0805', 'C17630'),
    ('100', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('100R 1% 0805', 'C17408'),
    ('1.8k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('1.8k 1% 0805', 'C17398'),
    ('3.3k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('3.3k 1% 0805', 'C114531'),
    ('10R', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('10R 1% 0805', 'C17415'),
    # ---- through-hole board ----
    ('100nF', 'C_Disc_D5.0mm_W2.5mm_P5.00mm'): ('100nF 50V X7R ceramic, 5.08 mm lead spacing', 'C84772'),
    ('10nF', 'C_Disc_D5.0mm_W2.5mm_P5.00mm'): ('10nF 50V X7R ceramic, 5.08 mm lead spacing', ''),
    ('1N5408', 'D_DO-201AD_P5.08mm_Vertical_KathodeUp'): ('1N5408 3A 1000V diode', 'C2460'),
    ('IRF9540N', 'TO-220-3_Vertical'): ('IRF9540NPBF P-MOSFET', 'C2575'),
    ('2N7000', 'TO-92_Inline_Wide'): ('2N7000 N-MOSFET', 'C232838'),
    ('10k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('10k 1% 1/4W metal film', 'C57436'),
    ('1k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('1k 1% 1/4W metal film', 'C57435'),
    ('1k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('1k 1% 1/4W metal film', 'C57435'),
    ('100k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('100k 1% 1/4W metal film', 'C58597'),
    ('330', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('330R 1% 1/4W metal film', 'C58608'),
    ('100', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('100R 1% 1/4W metal film', 'C57438'),
    ('10R', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('10R 1% 1/4W metal film', 'C57437'),
    ('1.8k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('1.8k 1% 1/4W metal film', ''),
    ('3.3k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('3.3k 1% 1/4W metal film', ''),
}

# Left off the JLCPCB order: A1 is two 15-pin sockets under one reference (JLCPCB places one part
# per reference), H1-H4 are bare mounting holes
NOT_PLACED = {'A1': 'two 15-pin 2.54 mm female headers for the Nano (LCSC C2897378), solder them yourself'}


def lcsc(value, footprint):
    """Part number for a value and footprint (library name optional), or ''."""
    return PARTS.get((value, footprint.split(':')[-1]), ('', ''))[1]
