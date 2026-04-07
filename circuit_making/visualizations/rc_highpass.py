from circuit_making.visualizations._common import draw_rc_highpass as _impl


def draw_rc_highpass(inputs: dict, outputs: dict):
    """Draw a clean rc highpass schematic with real values near components."""
    return _impl(inputs, outputs, title="RC High-Pass")
