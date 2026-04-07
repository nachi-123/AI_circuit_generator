from circuit_making.visualizations._common import draw_rlc_series_bandpass as _impl


def draw_rlc_series_bandpass(inputs: dict, outputs: dict):
    """Draw a clean rlc series bandpass schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="RLC Series Band-Pass")
