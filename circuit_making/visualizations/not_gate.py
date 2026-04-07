from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_not_gate(inputs: dict, outputs: dict):
    """Draw a clean not gate schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, gate="not", title="NOT Gate")
