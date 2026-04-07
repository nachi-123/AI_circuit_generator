from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_xnor(inputs: dict, outputs: dict):
    """Draw an XNOR gate schematic with connected inputs and side value labels."""
    return _impl(inputs, outputs, gate="xnor", title="XNOR Gate")
