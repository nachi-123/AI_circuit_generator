from circuit_making.visualizations._common import draw_opamp_family as _impl


def draw_non_inverting(inputs: dict, outputs: dict):
    """Draw a clean non inverting schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Non-Inverting Amplifier")
