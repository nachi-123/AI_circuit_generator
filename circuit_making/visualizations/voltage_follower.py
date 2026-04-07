from circuit_making.visualizations._common import draw_voltage_follower as _impl


def draw_voltage_follower(inputs: dict, outputs: dict):
    """Draw a clean voltage follower schematic with labeled inputs/outputs."""
    return _impl(inputs, outputs, title="Voltage Follower")
