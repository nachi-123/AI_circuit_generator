from circuit_making.visualizations._common import draw_down_counter as _impl


def draw_down_counter(inputs: dict, outputs: dict):
    """Draw a dedicated down counter schematic with element-local labels."""
    return _impl(inputs, outputs, title="Down Counter")
