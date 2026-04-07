"""
End-to-end circuit design workflow:
1. Parse user intent with Ollama
2. Predict circuit parameters with ML models
3. Generate circuit visualization
4. Return results (inputs, outputs, diagram path)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import ollama_trial as ot
from circuit_making.draw_circuit import draw_circuit_topology


def generate_circuit_from_description(
    user_description: str,
    save_dir: Path = Path("outputs"),
    show: bool = True,
    transparent: bool = False,
) -> dict[str, Any]:
    """
    End-to-end workflow: description → parameters → model prediction → visualization.

    Args:
        user_description: Natural language description of the circuit user wants
                         e.g., "Design a common emitter BJT amplifier with gain 20"
        save_dir: Directory to save the circuit diagram
        show: Whether to display the diagram window
        transparent: Whether to save with transparent background

    Returns:
        Dictionary with:
        - topology: Detected circuit topology name
        - direction: forward or backward
        - inputs: Dict of input parameter names and values used
        - outputs: Dict of output parameter names and predicted values
        - diagram_path: Path to saved circuit diagram
        - auto_filled_params: List of parameters auto-filled with defaults
    """
    # ===== PHASE 1: INTENT DETECTION & PARAMETER COLLECTION =====
    print(f"\n{'='*60}")
    print("PHASE 1: Intent Detection & Parameter Collection")
    print(f"{'='*60}")
    print(f"User request: {user_description}\n")

    # Discover available models and datasets
    catalog = ot.discover_models()
    inventory = ot.discover_model_inventory()
    data_cols = ot.load_dataset_columns()
    aliases = ot.alias_map(catalog, inventory)

    if not catalog["forward"] and not catalog["backward"]:
        raise RuntimeError("No models found in models/ folder.")

    # Detect intent from user description
    circuit_key, direction, provided, ask = ot.detect_intent(
        user_description, catalog, aliases, inventory
    )
    domain_hint = ot.classify_request_domain(user_description, provided)

    print(f"Detected domain: {domain_hint}")

    # Select appropriate model
    choice: ot.ModelChoice | None = None
    if circuit_key:
        choice = ot.best_choice_for_circuit(
            circuit_key, direction, catalog, data_cols, provided, domain_hint
        )
        if choice and choice.direction != direction:
            print(
                f"Direction adjusted to {choice.direction} based on provided parameters "
                f"for {ot.pretty_label(choice.key)}."
            )
    else:
        choice = ot.best_choice_from_all_models(
            direction, catalog, data_cols, provided, domain_hint
        )
        if choice:
            print(
                "Circuit name not explicit; auto-selected "
                f"{ot.pretty_label(choice.key)} ({choice.direction}) from parameter overlap."
            )

    # Try fuzzy keyword matching on original description if auto-detection failed
    if not choice:
        circuit_key = ot.keyword_match(user_description, aliases)
        if not circuit_key:
            circuit_key = ot.normalize_key(user_description)
        if circuit_key in (set(catalog["forward"].keys()) | set(catalog["backward"].keys())):
            choice = ot.select_model(circuit_key, direction, catalog)
            if choice:
                print(
                    f"Circuit detected from keywords: {ot.pretty_label(choice.key)} ({choice.direction})"
                )

    # Keep asking until user provides a valid circuit (only in interactive mode)
    attempt = 0
    while not choice:
        attempt += 1
        if attempt == 1 and ask:
            print(ask)
        else:
            if attempt > 1:
                print("\nInvalid circuit name. Please try again.")
            print("Available circuits include:")
            all_keys = sorted(set(catalog["forward"].keys()) | set(catalog["backward"].keys()))
            print(", ".join(ot.pretty_label(k) for k in all_keys))

        try:
            user_text = input("Please specify the circuit name: ").strip()
        except EOFError:
            raise RuntimeError(
                "Circuit could not be auto-detected and input is not interactive. "
                f"Auto-detected: domain={domain_hint}, provided_params={provided}"
            )
        
        circuit_key = ot.keyword_match(user_text, aliases)
        if not circuit_key:
            circuit_key = ot.normalize_key(user_text)
        if circuit_key in (set(catalog["forward"].keys()) | set(catalog["backward"].keys())):
            choice = ot.select_model(circuit_key, direction, catalog)

    if not choice:
        raise RuntimeError("No suitable model found for the request.")

    # Check for rule-based digital circuits
    if ot.maybe_run_rule_based_digital(choice.key, user_description, provided):
        raise RuntimeError("Rule-based circuit executed; cannot continue with ML prediction.")

    dataset_cols_for_choice = ot.dataset_cols_for_circuit(choice.key, data_cols)
    required_inputs, known_outputs = ot.infer_io_fields(choice, dataset_cols_for_choice)

    print(f"\nSelected: {ot.pretty_label(choice.key)}")
    print(f"Direction: {choice.direction}")
    print(f"Model: {choice.path.name}")
    print(f"Required parameters: {', '.join(required_inputs)}")
    if known_outputs:
        print(f"Predicted outputs: {', '.join(known_outputs)}")

    # Map provided parameters to required
    provided_for_choice, invalid_for_choice = ot.map_provided_to_required(
        required_inputs, provided
    )
    if invalid_for_choice:
        print(
            f"\nIgnored parameters (not valid for {ot.pretty_label(choice.key)}): "
            + ", ".join(invalid_for_choice)
        )

    missing_initial = [p for p in required_inputs if p not in provided_for_choice]
    if missing_initial:
        print(f"\nCan provide parameters from: {', '.join(missing_initial)}")

    # Collect missing parameters with defaults
    values, auto_filled = ot.collect_missing_params(
        required_inputs,
        provided_for_choice,
        choice.key,
        data_cols,
    )

    # Retry if prediction fails
    attempt = 0
    while True:
        attempt += 1
        try:
            prediction = ot.run_prediction(choice, required_inputs, values)
            break
        except ValueError as exc:
            if attempt > 2:
                raise
            print(f"\n{exc}")
            print("Please provide missing required values.")
            values, extra_auto = ot.collect_missing_params(
                required_inputs,
                values,
                choice.key,
                data_cols,
                force_prompt=True,
                allow_autofill=False,
            )
            auto_filled.extend(p for p in extra_auto if p not in auto_filled)

    # ===== PHASE 2: MODEL PREDICTION =====
    print(f"\n{'='*60}")
    print("PHASE 2: Model Prediction")
    print(f"{'='*60}")

    print("\nInputs used for prediction:")
    for name in required_inputs:
        print(f"  {name}: {ot.format_numeric_value(values[name])}")

    # Check model sensitivity
    insensitive = ot.model_looks_insensitive(choice, required_inputs, values, prediction)
    if insensitive:
        fallback = ot.dataset_nearest_fallback_prediction(
            choice.key, required_inputs, known_outputs, values
        )
        if fallback is not None and len(fallback) == len(prediction):
            print("\n⚠ Model appears insensitive; using dataset-nearest fallback instead.")
            prediction = fallback

    # Infer output names
    output_names = known_outputs
    if not output_names:
        output_names = ot.infer_output_names_from_counterpart(choice, catalog, len(prediction))

    print("\nPredicted outputs:")
    for name, val in zip(output_names, prediction.astype(float).flatten()):
        print(f"  {name}: {ot.format_numeric_value(val)}")

    if auto_filled:
        print(f"\nAuto-filled parameters: {', '.join(sorted(set(auto_filled)))}")

    # ===== PHASE 3: VISUALIZATION =====
    print(f"\n{'='*60}")
    print("PHASE 3: Circuit Visualization")
    print(f"{'='*60}")

    # Prepare input/output dicts for drawing
    inputs_dict = dict(values)  # All required inputs
    outputs_dict = {name: float(val) for name, val in zip(output_names, prediction)}

    # Normalize digital circuit values to binary (0 or 1)
    inputs_dict, outputs_dict = ot.normalize_digital_values(
        inputs_dict, outputs_dict, choice.key
    )

    # For supported digital circuits, display output values from truth tables
    # using the displayed binary inputs (keeps panel values consistent).
    outputs_dict = ot.override_digital_outputs_for_display(
        choice.key, inputs_dict, outputs_dict
    )

    # Normalize topology name for visualization lookup
    viz_topology = ot.normalize_key(choice.key)

    # Generate output filename
    save_dir.mkdir(parents=True, exist_ok=True)
    diagram_filename = f"{viz_topology}_predicted.png"
    save_path = save_dir / diagram_filename

    print(f"Generating visualization: {ot.pretty_label(choice.key)}")
    print(f"Saving to: {save_path}")

    try:
        diagram_path = draw_circuit_topology(
            viz_topology,
            inputs_dict,
            outputs_dict,
            save_path,
            show=show,
            transparent=transparent,
        )
        print(f"✓ Diagram saved successfully")
    except Exception as e:
        print(f"⚠ Warning: Could not generate visualization: {e}")
        diagram_path = None

    # ===== RETURN RESULTS =====
    print(f"\n{'='*60}")
    print("WORKFLOW COMPLETE")
    print(f"{'='*60}\n")

    return {
        "topology": choice.key,
        "direction": choice.direction,
        "inputs": inputs_dict,
        "outputs": outputs_dict,
        "diagram_path": str(diagram_path) if diagram_path else None,
        "auto_filled_params": auto_filled,
        "required_inputs": required_inputs,
        "output_names": output_names,
    }


def main() -> None:
    """CLI entry point for end-to-end workflow."""
    parser = argparse.ArgumentParser(
        description="Circuit design workflow: intent → parameters → prediction → visualization"
    )
    parser.add_argument(
        "description",
        nargs="?",
        help="Natural language description of the circuit (e.g., 'BJT amplifier with gain 20')",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default="outputs",
        help="Directory to save circuit diagrams (default: outputs/)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display diagram window after generating",
    )
    parser.add_argument(
        "--transparent",
        action="store_true",
        help="Save diagram with transparent background",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Save results as JSON to this file",
    )

    args = parser.parse_args()

    # Get user description
    if args.description:
        user_description = args.description
    else:
        print("Circuit Design Workflow")
        print("Describe the circuit you want to design.")
        print("Example: 'A BJT common emitter amplifier with voltage gain of 20'")
        user_description = input("\nWhat circuit do you want to generate? ").strip()

    if not user_description:
        print("Error: Empty request. Please provide a circuit description.")
        sys.exit(1)

    try:
        # Run the workflow
        results = generate_circuit_from_description(
            user_description,
            save_dir=Path(args.save_dir),
            show=args.show,
            transparent=args.transparent,
        )

        # Optionally save results as JSON
        if args.output_json:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Convert numpy arrays to serializable format
            json_results = dict(results)
            json_results["inputs"] = {k: float(v) for k, v in results["inputs"].items()}
            json_results["outputs"] = {k: float(v) for k, v in results["outputs"].items()}
            with open(output_path, "w") as f:
                json.dump(json_results, f, indent=2)
            print(f"Results saved to: {output_path}")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
