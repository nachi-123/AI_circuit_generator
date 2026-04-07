"""Production helpers to draw a selected circuit topology."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Callable

import pandas as pd

import ollama_trial as ot


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def normalize_topology_name(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("__", "_")
    )


def _get_draw_function(topology: str) -> Callable[[dict, dict], object]:
    aliases: dict[str, tuple[str, str]] = {
        "cb": ("bjt_cb", "draw_bjt_cb"),
        "cc": ("bjt_cc", "draw_bjt_cc"),
        "ce": ("bjt_ce", "draw_bjt_ce"),
        "cd": ("mosfet_cd", "draw_mosfet_cd"),
        "cg": ("mosfet_cg", "draw_mosfet_cg"),
        "cs": ("mosfet_cs", "draw_mosfet_cs"),
        "xor_gate": ("xor_2input", "draw_xor_2input"),
        "xnor_gate": ("xnor_2input", "draw_xnor_2input"),
    }

    module_key, function_name = aliases.get(topology, (topology, f"draw_{topology}"))
    module_name = f"circuit_making.visualizations.{module_key}"
    module = importlib.import_module(module_name)
    return getattr(module, function_name)


def _best_dataset_path(topology_key: str) -> Path | None:
    if not ot.DATASET_DIR.exists():
        return None

    topo = normalize_topology_name(topology_key)
    exact_match: Path | None = None
    suffix_match: Path | None = None
    contains_match: Path | None = None

    for csv_path in sorted(ot.DATASET_DIR.rglob("*.csv"), key=lambda p: str(p).lower()):
        stem_key = ot.dataset_key_from_stem(csv_path.stem)
        if stem_key == topo:
            exact_match = csv_path
            break
        if stem_key.endswith(f"_{topo}"):
            suffix_match = suffix_match or csv_path
        if f"_{topo}_" in stem_key:
            contains_match = contains_match or csv_path

    return exact_match or suffix_match or contains_match


def _coerce_scalar(value: object) -> object:
    if value is None:
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _dataset_example_inputs(topology_key: str) -> dict[str, object]:
    csv_path = _best_dataset_path(topology_key)
    if not csv_path:
        return {}

    try:
        first = pd.read_csv(csv_path, nrows=1)
    except Exception:
        return {}

    if first.empty:
        return {}

    row = first.iloc[0].to_dict()
    row = {str(k): _coerce_scalar(v) for k, v in row.items()}

    catalog = ot.discover_models()
    data_cols = ot.load_dataset_columns()

    model_choice = ot.select_model(topology_key, "forward", catalog)
    if not model_choice:
        model_choice = ot.select_model(topology_key, "backward", catalog)

    if not model_choice:
        return row

    dataset_cols = data_cols.get(model_choice.key)
    required_inputs, _ = ot.infer_io_fields(model_choice, dataset_cols)
    if not required_inputs:
        return row

    filtered = {k: row[k] for k in required_inputs if k in row}
    return filtered or row


def _enrich_inputs_with_dataset_example(topology_key: str, inputs: dict) -> tuple[dict, dict]:
    example_inputs = _dataset_example_inputs(topology_key)
    if not example_inputs:
        return dict(inputs), {}

    # Fill only missing fields from dataset example; preserve actual predicted/provided values.
    merged_inputs = {**example_inputs, **inputs}
    return merged_inputs, example_inputs


def draw_circuit_topology(
    topology: str,
    inputs: dict,
    outputs: dict,
    save_path: Path,
    show: bool,
    transparent: bool,
) -> Path:
    topology_key = normalize_topology_name(topology)
    draw_fn = _get_draw_function(topology_key)

    if transparent and save_path.suffix.lower() not in {".png", ".svg"}:
        save_path = save_path.with_suffix(".png")

    rendered_inputs, _ = _enrich_inputs_with_dataset_example(topology_key, inputs)
    drawing = draw_fn(rendered_inputs, outputs)

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # schemdraw SVG backend only supports saving SVG.
    if save_path.suffix.lower() == ".png":
        save_path_for_draw = save_path.with_suffix(".svg")
    else:
        save_path_for_draw = save_path

    drawing.save(str(save_path_for_draw), transparent=transparent)

    if show:
        drawing.draw()

    print(f"Topology: {topology_key}")
    print(f"Transparent background: {transparent}")
    print(f"Diagram saved to: {save_path_for_draw}")
    return save_path_for_draw


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw a selected circuit topology diagram.")
    parser.add_argument("--topology", type=str, required=True, help="Topology key, e.g. and_gate")
    parser.add_argument("--inputs", type=str, default="{}", help="JSON string of input features")
    parser.add_argument("--outputs", type=str, default="{}", help="JSON string of predicted outputs")
    parser.add_argument("--save", type=str, default="outputs/circuit.svg", help="Output image path")
    parser.add_argument(
        "--transparent",
        action="store_true",
        help="Save image with transparent background",
    )
    parser.add_argument("--show", action="store_true", help="Display drawing window")

    args = parser.parse_args()
    inputs = json.loads(args.inputs)
    outputs = json.loads(args.outputs)
    save_path = Path(args.save)

    draw_circuit_topology(
        args.topology,
        inputs,
        outputs,
        save_path,
        show=args.show,
        transparent=args.transparent,
    )


if __name__ == "__main__":
    main()
