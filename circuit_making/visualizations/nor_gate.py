from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_nor_gate(inputs: dict, outputs: dict):
    """Draw a clean nor gate schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, gate="nor", title="NOR Gate")
