from circuit_making.visualizations._common import draw_up_counter as _impl


def draw_up_counter(inputs: dict, outputs: dict):
    """Draw a reference-aligned up counter schematic with local labels."""
    return _impl(inputs, outputs, title="Up Counter")
