from circuit_making.visualizations._common import draw_mux as _impl


def draw_mux(inputs: dict, outputs: dict):
    """Draw a clean 4:1 multiplexer schematic with labeled inputs/outputs and no side panels."""
    return _impl(inputs, outputs, title="4:1 Multiplexer")

