from circuit_making.visualizations._common import draw_clipper as _impl


def draw_clipper(inputs: dict, outputs: dict):
    """Draw a clean clipper schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Clipper")
