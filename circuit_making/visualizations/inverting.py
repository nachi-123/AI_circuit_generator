from circuit_making.visualizations._common import draw_inverting as _impl


def draw_inverting(inputs: dict, outputs: dict):
    """Draw a clean inverting schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Inverting Amplifier")
