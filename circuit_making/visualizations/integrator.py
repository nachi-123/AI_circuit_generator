from circuit_making.visualizations._common import draw_integrator_custom as _impl


def draw_integrator(inputs: dict, outputs: dict):
    """Draw an integrator using centralized common visualization logic."""
    return _impl(inputs, outputs)
