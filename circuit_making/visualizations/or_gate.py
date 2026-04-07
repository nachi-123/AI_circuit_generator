from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_or_gate(inputs: dict, outputs: dict):
    """Draw a clean or gate schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, gate="or", title="OR Gate")
