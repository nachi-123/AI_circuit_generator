from circuit_making.visualizations._common import draw_rc_lowpass as _impl


def draw_rc_lowpass(inputs: dict, outputs: dict):
    """Draw a clean rc lowpass schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="RC Low-Pass")
