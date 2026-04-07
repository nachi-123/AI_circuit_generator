from __future__ import annotations

from circuit_making.visualizations._common import draw_log_amplifier


def draw_antilog_amplifier(inputs: dict, outputs: dict):
    """Draw antilog amplifier using shared op-amp style implementation."""
    return draw_log_amplifier(
        inputs,
        outputs,
        title="Antilog Amplifier",
        swap_resistor_diode=True,
    )