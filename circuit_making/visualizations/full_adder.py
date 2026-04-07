from circuit_making.visualizations._common import draw_full_adder as _impl


def draw_full_adder(inputs: dict, outputs: dict):
    """Draw a clean full adder schematic with labeled inputs/outputs and no side panels."""
    return _impl(inputs, outputs, title="Full Adder")

