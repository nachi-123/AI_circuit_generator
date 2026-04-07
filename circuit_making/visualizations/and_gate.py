from circuit_making.visualizations._common import draw_logic_gate as _impl


def draw_and_gate(inputs: dict, outputs: dict):
    """Draw a clean and gate schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, gate="and", title="AND Gate")
