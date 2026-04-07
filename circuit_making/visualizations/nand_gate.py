from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_nand_gate(inputs: dict, outputs: dict):
    """Draw a clean nand gate schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, gate="nand", title="NAND Gate")
