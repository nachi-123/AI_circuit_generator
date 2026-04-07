from circuit_making.visualizations._common import draw_differentiator as _impl


def draw_differentiator(inputs: dict, outputs: dict):
    """Draw a clean differentiator schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Differentiator")
