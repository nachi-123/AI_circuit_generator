from circuit_making.visualizations._common import draw_rl_highpass as _impl


def draw_rl_highpass(inputs: dict, outputs: dict):
    """Draw a clean rl highpass schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="RL High-Pass")
