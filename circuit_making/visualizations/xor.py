from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_xor(inputs: dict, outputs: dict):
    """Draw an XOR gate schematic with connected inputs and side value labels."""
    return _impl(inputs, outputs, gate="xor", title="XOR Gate")
