from circuit_making.visualizations._common import draw_bjt_ce as _impl


def draw_bjt_ce(inputs: dict, outputs: dict):
    """Draw a reference-aligned BJT CE schematic with element-local values."""
    return _impl(inputs, outputs, title="BJT Common-Emitter")
