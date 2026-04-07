from circuit_making.visualizations._common import draw_log_amplifier as _impl


def draw_log_amplifier(inputs: dict, outputs: dict):
    """Draw a clean log amplifier schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Log Amplifier")
