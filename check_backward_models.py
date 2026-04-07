from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ollama_trial as ot
from circuit_making.draw_circuit import draw_circuit_topology


DIGITAL_TARGET_HINTS = {
    "y",
    "y0",
    "y1",
    "y2",
    "y3",
    "sum",
    "carry",
    "borrow",
    "diff",
    "valid",
    "out",
    "output",
}


def _default_target_value(param: str) -> float:
    """Best-effort default for backward target fields."""
    nk = ot.normalize_key(param)
    if nk in DIGITAL_TARGET_HINTS:
        return 1.0
    guessed = ot.resolve_default_value(param, {})
    if guessed is not None:
        return float(guessed)
    return 1.0


def list_backward_models() -> list[str]:
    catalog = ot.discover_models()
    return sorted(catalog["backward"].keys())


def run_backward_model(
    model_key: str,
    targets: dict[str, float],
    save_dir: Path,
    show: bool = False,
    transparent: bool = False,
) -> dict[str, Any]:
    catalog = ot.discover_models()
    data_cols = ot.load_dataset_columns()

    choice = ot.select_model(model_key, "backward", catalog)
    if not choice:
        raise RuntimeError(f"Backward model not found for key: {model_key}")

    required_inputs, known_outputs = ot.infer_io_fields(choice, data_cols.get(choice.key))

    values: dict[str, float] = {}
    for req in required_inputs:
        if req in targets:
            values[req] = float(targets[req])
        else:
            values[req] = _default_target_value(req)

    prediction = ot.run_prediction(choice, required_inputs, values)

    output_names = known_outputs
    if not output_names:
        output_names = ot.infer_output_names_from_counterpart(choice, catalog, len(prediction))

    # In backward models, predicted values are usually circuit inputs.
    predicted_inputs = {
        name: float(val) for name, val in zip(output_names, prediction.astype(float).flatten())
    }
    target_outputs = dict(values)

    # Normalize display values for digital circuits.
    predicted_inputs, target_outputs = ot.normalize_digital_values(
        predicted_inputs, target_outputs, choice.key
    )
    target_outputs = ot.override_digital_outputs_for_display(
        choice.key, predicted_inputs, target_outputs
    )

    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{ot.normalize_key(choice.key)}_backward.svg"

    diagram_path = draw_circuit_topology(
        topology=ot.normalize_key(choice.key),
        inputs=predicted_inputs,
        outputs=target_outputs,
        save_path=save_path,
        show=show,
        transparent=transparent,
    )

    return {
        "model_key": choice.key,
        "model_file": choice.path.name,
        "required_targets": required_inputs,
        "targets_used": values,
        "predicted_inputs": predicted_inputs,
        "diagram_path": str(diagram_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backward models in explicit order.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List backward model keys in sorted order and exit",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Backward model key, e.g. and_gate",
    )
    parser.add_argument(
        "--targets",
        type=str,
        default="{}",
        help='JSON dict of backward target fields, e.g. {"Y":1}',
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Single target as key=value. Can be repeated, e.g. --target Y=1 --target Cin=0",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default="outputs/backward_checks",
        help="Folder to save generated diagram",
    )
    parser.add_argument("--show", action="store_true", help="Show diagram window")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")

    args = parser.parse_args()

    if args.list:
        models = list_backward_models()
        for i, key in enumerate(models, start=1):
            print(f"{i:02d}. {key}")
        return

    if not args.model:
        raise SystemExit("Provide --model or use --list")

    parsed_targets: dict[str, Any] = {}
    if args.target:
        for item in args.target:
            if "=" not in item:
                raise SystemExit(f"Invalid --target format: {item}. Use key=value")
            key, raw_val = item.split("=", 1)
            key = key.strip()
            raw_val = raw_val.strip()
            if not key:
                raise SystemExit(f"Invalid --target key in: {item}")
            try:
                parsed_targets[key] = float(raw_val)
            except Exception as exc:
                raise SystemExit(f"Invalid numeric value in --target '{item}': {exc}")
    else:
        try:
            parsed_targets = json.loads(args.targets)
            if not isinstance(parsed_targets, dict):
                raise ValueError("--targets must be a JSON object")
        except Exception as exc:
            raise SystemExit(f"Invalid --targets JSON: {exc}")

    normalized_targets = {str(k): float(v) for k, v in parsed_targets.items()}

    result = run_backward_model(
        model_key=ot.normalize_key(args.model),
        targets=normalized_targets,
        save_dir=Path(args.save_dir),
        show=args.show,
        transparent=args.transparent,
    )

    print("\nBackward check complete")
    print(f"Model: {result['model_key']} ({result['model_file']})")
    print("Required targets: " + ", ".join(result["required_targets"]))
    print("Targets used:")
    for k, v in result["targets_used"].items():
        print(f"  {k}: {ot.format_numeric_value(v)}")
    print("Predicted inputs:")
    for k, v in result["predicted_inputs"].items():
        print(f"  {k}: {ot.format_numeric_value(v)}")
    print(f"Diagram: {result['diagram_path']}")


if __name__ == "__main__":
    main()
