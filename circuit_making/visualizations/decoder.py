from circuit_making.visualizations._common import draw_decoder as _impl


def draw_decoder(inputs: dict, outputs: dict):
    """Draw a clean decoder schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="2 x 4 Decoder")
