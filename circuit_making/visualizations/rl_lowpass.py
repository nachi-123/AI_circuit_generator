from circuit_making.visualizations._common import draw_rl_lowpass as _impl


def draw_rl_lowpass(inputs: dict, outputs: dict):
    """Draw a clean rl lowpass schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="RL Low-Pass")
