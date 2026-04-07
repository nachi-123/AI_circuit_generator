from circuit_making.visualizations._common import draw_bjt_cc as _impl


def draw_bjt_cc(inputs: dict, outputs: dict):
    """Draw a clean bjt cc schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="BJT Common-Collector")
