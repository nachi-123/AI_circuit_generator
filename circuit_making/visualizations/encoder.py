from circuit_making.visualizations._common import draw_encoder as _impl


def draw_encoder(inputs: dict, outputs: dict):
    """Draw a dedicated encoder schematic with element-local labels and no side panel."""
    return _impl(inputs, outputs, title="4 x 2 Encoder")
