from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import ollama_trial as ot
from circuit_making.draw_circuit import draw_circuit_topology


REQUESTED_TOPOLOGIES = [
    "nor_gate",
    "not_gate",
    "or_gate",
    "priority_encoder",
    "rc_highpass",
    "rc_lowpass",
    "rl_lowpass",
    "rlc_parallel_bandpass",
    "rlc_series_bandpass",
]

SOURCE_BASED_TOPOLOGIES = {
    "rc_highpass",
    "rc_lowpass",
    "rl_lowpass",
    "rlc_parallel_bandpass",
    "rlc_series_bandpass",
}


def _forward_choice_for(topology: str, catalog: dict[str, dict[str, Path]]) -> ot.ModelChoice:
    if topology not in catalog["forward"]:
        raise RuntimeError(
            f"Forward model missing for '{topology}'. "
            "This script requires forward models so real component/input values can be drawn."
        )
    return ot.ModelChoice(key=topology, direction="forward", path=catalog["forward"][topology])


def _autofill_inputs(required_inputs: list[str], topology: str, data_cols: dict[str, list[str]]) -> dict[str, float]:
    defaults = ot.load_default_values_from_dataset(topology, data_cols)
    values: dict[str, float] = {}

    for name in required_inputs:
        default_val = ot.resolve_default_value(name, defaults)
        if default_val is None:
            raise RuntimeError(
                f"No default value found for required input '{name}' in topology '{topology}'."
            )
        values[name] = float(default_val)

    return values


def _predict_for_topology(
    topology: str,
    catalog: dict[str, dict[str, Path]],
    data_cols: dict[str, list[str]],
) -> tuple[dict[str, float], dict[str, float], ot.ModelChoice]:
    choice = _forward_choice_for(topology, catalog)

    dataset_cols = data_cols.get(topology)
    required_inputs, known_outputs = ot.infer_io_fields(choice, dataset_cols)

    inputs = _autofill_inputs(required_inputs, topology, data_cols)
    prediction = ot.run_prediction(choice, required_inputs, inputs)
    prediction_arr = np.array(prediction, dtype=float).flatten()

    output_names = known_outputs
    if not output_names:
        output_names = ot.infer_output_names_from_counterpart(choice, catalog, len(prediction_arr))

    outputs = {
        name: float(value)
        for name, value in zip(output_names, prediction_arr)
    }

    return inputs, outputs, choice


def _build_draw_inputs(
    topology: str,
    predicted_inputs: dict[str, float],
    data_cols: dict[str, list[str]],
) -> dict[str, float]:
    draw_inputs = dict(predicted_inputs)

    # Some forward models do not include source amplitude, but the diagram has a source symbol.
    # In that case inject a numeric Vin from dataset/global defaults so labels are never plain variables.
    if topology in SOURCE_BASED_TOPOLOGIES and not any(k in draw_inputs for k in ("Vin", "Vin_V")):
        defaults = ot.load_default_values_from_dataset(topology, data_cols)
        vin_default = ot.resolve_default_value("vin", defaults)
        if vin_default is None:
            vin_default = 1.0
        draw_inputs["Vin"] = float(vin_default)

    return draw_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict and draw circuit topologies.")
    parser.add_argument("--topology", type=str, help="Run only for a specific topology.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/reference_topologies_test"), help="Output directory.")
    parser.add_argument("--show", action="store_true", help="Show the diagrams instead of saving.")
    parser.add_argument("--transparent", action="store_true", help="Save with a transparent background.")
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(exist_ok=True, parents=True)

    print(f"Loading model catalog...")
    catalog = ot.discover_models()
    print(f"Loading dataset column info...")
    data_cols = ot.load_dataset_columns()

    topologies_to_run = [args.topology] if args.topology else REQUESTED_TOPOLOGIES

    for topology in topologies_to_run:
        print(f"Processing: {topology}")
        try:
            inputs, outputs, choice = _predict_for_topology(topology, catalog, data_cols)
            draw_inputs = _build_draw_inputs(topology, inputs, data_cols)

            print(f"  Inputs: {draw_inputs}")
            print(f"  Outputs: {outputs}")

            draw_circuit_topology(
                topology,
                draw_inputs,
                outputs,
                save_path=out_dir / f"{topology}.svg",
                show=args.show,
                transparent=args.transparent
            )

        except Exception as e:
            print(f"  ERROR: Failed to process {topology}: {e}")


if __name__ == "__main__":
    main()
