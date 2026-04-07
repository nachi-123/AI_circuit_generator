from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import numpy as np

import ollama_trial as ot
from circuit_making.draw_circuit import draw_circuit_topology


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHAT_OUTPUTS_DIR = OUTPUTS_DIR / "chat"

# Ensure output directories exist before mounting static files
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CHAT_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str
    topology: str | None = None
    direction: str | None = None
    inputs: dict[str, float] = Field(default_factory=dict)
    outputs: dict[str, float] = Field(default_factory=dict)
    auto_filled: list[str] = Field(default_factory=list)
    ignored_params: list[str] = Field(default_factory=list)
    image_url: str | None = None
    download_url: str | None = None


@dataclass
class AppState:
    catalog: dict[str, dict[str, Path]]
    inventory: dict[str, list[Path]]
    data_cols: dict[str, list[str]]
    aliases: dict[str, str]


app = FastAPI(title="AI Circuit Assistant")


@app.on_event("startup")
def _startup() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    catalog = ot.discover_models()
    inventory = ot.discover_model_inventory()
    data_cols = ot.load_dataset_columns()
    aliases = ot.alias_map(catalog, inventory)

    app.state.ctx = AppState(
        catalog=catalog,
        inventory=inventory,
        data_cols=data_cols,
        aliases=aliases,
    )


# Serve generated artifacts (SVGs) so the chat can open/download them.
app.mount("/files", StaticFiles(directory=str(OUTPUTS_DIR), html=False), name="files")


def _autofill_required_inputs(
    required_inputs: list[str],
    circuit_key: str,
    dataset_cols: dict[str, list[str]],
    provided_for_choice: dict[str, float],
) -> tuple[dict[str, float], list[str], list[str]]:
    """Non-interactive version of filling model inputs.

    - Uses user-provided values when present
    - Otherwise uses dataset defaults
    - If no default exists, returns the missing list
    """
    values: dict[str, float] = {}
    auto_filled: list[str] = []
    missing: list[str] = []

    defaults: dict[str, float] = {}
    try:
        defaults = ot.load_default_values_from_dataset(circuit_key, dataset_cols)
    except Exception:
        defaults = {}

    for name in required_inputs:
        if name in provided_for_choice:
            values[name] = float(provided_for_choice[name])
            continue
        default_val = ot.resolve_default_value(name, defaults)
        if default_val is None:
            missing.append(name)
            continue
        values[name] = float(default_val)
        auto_filled.append(name)

    return values, auto_filled, missing


def _render_reply(
    topology: str,
    direction: str,
    outputs: dict[str, float],
    image_url: str | None,
    auto_filled: list[str],
    ignored: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"Topology: {topology} ({direction})")
    if outputs:
        lines.append("Outputs:")
        for k, v in outputs.items():
            lines.append(f"- {k}: {ot.format_numeric_value(v)}")
    if auto_filled:
        lines.append("Auto-filled inputs: " + ", ".join(sorted(set(auto_filled))))
    if ignored:
        lines.append("Ignored params: " + ", ".join(sorted(set(ignored))))
    if image_url:
        lines.append("Diagram: " + image_url)
    return "\n".join(lines)


def _has_explicit_direction_request(user_text: str, direction: str) -> bool:
    text = user_text.lower()
    if direction == "backward":
        markers = (
            "backward",
            "inverse",
            "reverse",
            "find inputs",
            "find input",
            "required values",
            "required input",
            "design for",
            "target",
        )
    else:
        markers = ("forward", "predict output", "find output", "what is output")
    return any(marker in text for marker in markers)


def _allows_autofill(user_text: str) -> bool:
    text = user_text.lower()
    markers = (
        "continue with autofill",
        "continue with auto fill",
        "use autofill",
        "use auto fill",
        "use defaults",
        "proceed with defaults",
        "autofill yes",
        "auto fill yes",
    )
    return any(marker in text for marker in markers)


def _run_forward_workflow(user_text: str) -> ChatResponse:
    ctx: AppState = app.state.ctx
    catalog = ctx.catalog
    inventory = ctx.inventory
    data_cols = ctx.data_cols
    aliases = ctx.aliases

    circuit_key, direction_guess, provided, ask = ot.detect_intent(user_text, catalog, aliases, inventory)
    domain_hint = ot.classify_request_domain(user_text, provided)

    if not circuit_key:
        msg = ask or "I couldn't detect the circuit. Please mention a topology name (e.g., priority_encoder, rc_lowpass) and any known parameters."
        return ChatResponse(reply=msg)

    requested_direction = direction_guess if direction_guess in ("forward", "backward") else "forward"
    explicit_direction = _has_explicit_direction_request(user_text, requested_direction)

    choice = ot.best_choice_for_circuit(circuit_key, requested_direction, catalog, data_cols, provided, domain_hint)
    if explicit_direction and choice and choice.direction != requested_direction:
        # Do not silently switch model direction when user explicitly asked for one.
        path = catalog.get(requested_direction, {}).get(circuit_key)
        if path:
            choice = ot.ModelChoice(key=circuit_key, direction=requested_direction, path=path)
        else:
            return ChatResponse(
                reply=(
                    f"No {requested_direction} model found for '{circuit_key}'. "
                    f"Available directions: "
                    + ", ".join(
                        d for d in ("forward", "backward") if circuit_key in catalog.get(d, {})
                    )
                ),
                topology=circuit_key,
                direction=requested_direction,
            )

    if not choice:
        return ChatResponse(
            reply=f"No {requested_direction} model found for '{circuit_key}'. Try a different topology name.",
            topology=circuit_key,
            direction=requested_direction,
        )

    direction = choice.direction

    dataset_cols = ot.dataset_cols_for_circuit(choice.key, data_cols)
    required_inputs, known_outputs = ot.infer_io_fields(choice, dataset_cols)

    provided_for_choice, ignored = ot.map_provided_to_required(required_inputs, provided)

    missing_initial = [name for name in required_inputs if name not in provided_for_choice]
    if missing_initial and not _allows_autofill(user_text):
        example_fields = " ".join(f"{name}=1.0" for name in missing_initial[:4])
        return ChatResponse(
            reply=(
                f"More inputs are needed for {choice.key}: {', '.join(missing_initial)}\n"
                f"Please provide all of them, or reply with 'continue with autofill' to use dataset defaults where available.\n"
                f"Example: {example_fields}"
            ),
            topology=choice.key,
            direction=direction,
            inputs=provided_for_choice,
            ignored_params=ignored,
        )

    values, auto_filled, missing = _autofill_required_inputs(required_inputs, choice.key, data_cols, provided_for_choice)
    if missing:
        example_fields = " ".join(f"{name}=1.0" for name in missing[:4])
        if not example_fields:
            example_fields = "<param>=<value>"
        return ChatResponse(
            reply=(
                f"Missing required inputs for {choice.key}: {', '.join(missing)}\n"
                f"Please provide those values in your message (example: {example_fields})."
            ),
            topology=choice.key,
            direction=direction,
            inputs=values,
            auto_filled=auto_filled,
            ignored_params=ignored,
        )

    prediction = ot.run_prediction(choice, required_inputs, values)
    prediction_arr = np.array(prediction, dtype=float).flatten()

    output_names = known_outputs
    if not output_names:
        output_names = ot.infer_output_names_from_counterpart(choice, catalog, len(prediction_arr))

    outputs = {name: float(val) for name, val in zip(output_names, prediction_arr)}

    # Generate diagram
    topology_key = ot.normalize_key(choice.key)
    file_id = uuid.uuid4().hex
    out_path = CHAT_OUTPUTS_DIR / f"{topology_key}_{file_id}.svg"
    draw_circuit_topology(
        topology_key,
        inputs=values,
        outputs=outputs,
        save_path=out_path,
        show=False,
        transparent=False,
    )

    rel = out_path.relative_to(OUTPUTS_DIR).as_posix()
    image_url = f"/files/{rel}"

    reply = _render_reply(choice.key, direction, outputs, image_url, auto_filled, ignored)
    return ChatResponse(
        reply=reply,
        topology=choice.key,
        direction=direction,
        inputs=values,
        outputs=outputs,
        auto_filled=auto_filled,
        ignored_params=ignored,
        image_url=image_url,
        download_url=image_url,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> HTMLResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("Missing web/index.html", status_code=500)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/static/{path:path}")
def static_files(path: str):
    file_path = WEB_DIR / path
    if not file_path.exists() or not file_path.is_file():
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(str(file_path))


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        return _run_forward_workflow(req.message)
    except Exception as exc:
        # Keep API responses JSON-shaped so frontend parsing does not fail.
        return ChatResponse(reply=f"Request failed: {exc}")
         