from circuit_making.visualizations._common import draw_clamper as _impl


def draw_clamper(inputs: dict, outputs: dict):
    """Draw a clean clamper schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Clamper")
