from circuit_making.visualizations._common import draw_demux as _impl


def draw_demux(inputs: dict, outputs: dict):
    """Draw a clean demux schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="1:4 DEMUX")
