from circuit_making.visualizations._common import draw_rlc_parallel_bandpass as _impl


def draw_rlc_parallel_bandpass(inputs: dict, outputs: dict):
    """Draw a clean rlc parallel bandpass schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="RLC Parallel Band-Pass")
