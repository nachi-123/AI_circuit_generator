from circuit_making.visualizations._common import draw_priority_encoder as _impl


def draw_priority_encoder(inputs: dict, outputs: dict):
    """Draw a clean priority encoder schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Priority Encoder")
