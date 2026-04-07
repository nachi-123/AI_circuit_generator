# Circuit Design Workflow Documentation

## Overview

The end-to-end workflow integrates three main components:

1. **Ollama Intent Parser** (`ollama_trial.py`): Understands natural language descriptions and detects circuit type
2. **ML Model Predictions** (`ollama_trial.py`): Predicts circuit parameters and output values
3. **Circuit Visualization** (`circuit_making/`): Generates and saves circuit diagrams

## Architecture

```
User Input (Natural Language)
    ↓
[PHASE 1] Intent Detection & Parameter Collection
  - Parse user description with intent detection
  - Extract provided parameters
  - Match to available circuit models
  - Collect missing parameters with defaults
    ↓
[PHASE 2] Model Prediction
  - Load appropriate ML model (forward/backward)
  - Make parameter predictions
  - Check model sensitivity
  - Return predicted outputs
    ↓
[PHASE 3] Visualization
  - Call topology-specific draw function
  - Generate circuit diagram
  - Save to outputs/ directory
    ↓
Results (Inputs + Outputs + Diagram)
```

## Usage

### 1. **Programmatic Usage (Python)**

```python
from end_to_end_workflow import generate_circuit_from_description
from pathlib import Path

# Generate a circuit with natural language description
results = generate_circuit_from_description(
    user_description="Design an AND gate circuit",
    save_dir=Path("outputs"),
    show=True,          # Display diagram window
    transparent=False   # Background transparency
)

# Results structure:
# {
#   "topology": "and_gate",
#   "direction": "forward",
#   "inputs": {"A": 1.0, "B": 0.0, ...},
#   "outputs": {"Y": 1.0},
#   "diagram_path": "outputs/and_gate_predicted.png",
#   "auto_filled_params": ["supply_voltage_V"],
#   "required_inputs": ["A", "B", ...],
#   "output_names": ["Y"]
# }
```

### 2. **CLI Usage (Command-Line)**

```bash
# Interactive mode (prompts for description)
python end_to_end_workflow.py

# Provide description as argument
python end_to_end_workflow.py "Design an RC lowpass filter"

# With options
python end_to_end_workflow.py "BJT amplifier with gain 50" \
    --save-dir outputs/amplifiers \
    --transparent \
    --no-show \
    --output-json results.json
```

### 3. **Example Scripts**

```bash
# Run example 1: Simple AND gate
python example_workflows.py 1

# Run example 2: RC low-pass filter
python example_workflows.py 2

# Run example 3: BJT amplifier
python example_workflows.py 3

# Run all examples
python example_workflows.py
```

## Workflow Phases

### **PHASE 1: Intent Detection & Parameter Collection**

1. **Intent Detection**
   - Parse user natural language description
   - Extract keyword parameters
   - Detect circuit domain (analog vs digital)
   - Infer direction (forward design or backward analysis)

2. **Model Selection**
   - Match detected circuit to available models
   - Choose appropriate direction (forward/backward)
   - Fall back to interactive user selection if needed

3. **Parameter Collection**
   - Extract explicitly provided parameters from user description
   - Collect missing parameters in priority order:
     1. Circuit-specific defaults from dataset
     2. Global parameter medians across all datasets
     3. Hardcoded engineering standards (5V, 25°C, etc.)
     4. Interactive user prompts

### **PHASE 2: Model Prediction**

1. **Load Model**
   - Load appropriate ML model from `models/models_forward/` or `models_backward/`
   - Verify all required input parameters available

2. **Make Prediction**
   - Construct input vector with required parameters
   - Run through ML model
   - Get predicted output values

3. **Sensitivity Check**
   - Heuristic: verify model actually changes outputs based on inputs
   - Fall back to dataset-nearest fallback prediction if model insensitive
   - Flag warnings if issues detected

### **PHASE 3: Visualization**

1. **Get Draw Function**
   - Normalize topology name (e.g., "and_gate")
   - Import visualization module: `circuit_making.visualizations.{topology}`
   - Get draw function: `draw_{topology}`

2. **Generate Diagram**
   - Pass inputs and predicted outputs to draw function
   - Draw function returns drawing object

3. **Save & Display**
   - Save to outputs directory with transparent/opaque background
   - Optionally display in window

## Supported Topologies

### Analog Circuits (30)
- **BJT**: CB, CC, CE configurations
- **MOSFET**: CD, CG, CS configurations  
- **Op-Amp**: Inverting, Non-inverting, Voltage Follower, Comparator
- **Filters**: RC Low-Pass, RL High-Pass, RL Low-Pass, RLC Band-Pass (series & parallel)
- **Rectifiers**: Half-wave, Full-wave
- **Other**: Clamper, Clipper, Differentiator, Integrator, Antilog Amplifier, Log Amplifier

### Digital Circuits (26)
- **Logic Gates**: AND, NAND, OR, NOR, NOT, XOR, XNOR
- **Combinational**: Full Adder, Half Adder, Full Subtractor, Half Subtractor, Mux, Demux, Encoder, Decoder, Comparator
- **Sequential**: Up Counter, Down Counter, Up/Down Counter, Mod-N Counter

## Data Structures

### Input Examples

```python
# Provide by user in description:
"Design a BJT amplifier with Av=50 and fH=100kHz"

# Extracted:
{
    "Av": 50.0,
    "fH": 100000.0
}

# Completed with defaults:
{
    "Av": 50.0,
    "fH": 100000.0,
    "Rc": 2000.0,      # from dataset default
    "Re": 500.0,       # from dataset default
    "Vcc": 5.0,        # from hardcoded standard
    "temperature": 25.0  # from hardcoded standard
}
```

### Output Examples

```python
# Model prediction for BJT CE amplifier:
{
    "Ic": 2.5,         # mA
    "Vce": 3.2,        # V
    "fL": 50.0         # Hz
}
```

## Default Value Fallback Chain

When a required parameter is missing, the workflow searches through these tiers:

1. **Circuit-Specific Defaults**: Median from matching dataset CSV
2. **Semantic Aliases**: Fuzzy match (e.g., "Valid" → "valid", "Vout" → "output_voltage")
3. **Global Medians**: Per-parameter median across ALL datasets
4. **Hardcoded Priors**: Standard engineering values
   - `valid = 1.0`
   - `supply_voltage_v = 5.0`
   - `temperature_c = 25.0`
   - `propagation_delay_ns = 10.0`
5. **Interactive Prompt**: Ask user if all above fail

## Error Handling

- **Missing Circuit**: User provides invalid circuit name → Shows available options
- **Missing Parameters**: Insufficient inputs → Auto-fill with defaults or prompt
- **Model Insensitivity**: Output doesn't change with inputs → Use dataset fallback
- **Visualization Error**: Draw function unavailable → Skip visualization, return prediction
- **Prediction Error**: Model fails → Retry with forced interactive parameter collection

## Output Directory Structure

```
outputs/
├── and_gate_predicted.png          # Generated diagrams
├── rc_lowpass_predicted.png
├── bjt_ce_predicted.png
├── results.json                     # Optional: full results as JSON
└── examples/
    ├── example1_logic.png
    ├── example2_filter.png
    └── example3_amplifier.png
```

## Integration Points

### For Web UI
```python
# Call from web backend
results = generate_circuit_from_description(
    user_description=request.form['description'],
    save_dir=Path(f"uploads/{user_id}"),
    show=False,
    transparent=True  # For overlay on HTML canvas
)

return {
    "topology": results['topology'],
    "prediction": results['outputs'],
    "diagram_url": f"/diagrams/{results['diagram_path']}"
}
```

### For Batch Processing
```python
# Process multiple descriptions
descriptions = [
    "AND gate with 5V supply",
    "BJT amplifier with gain 20",
    "RC filter with 1k resistor"
]

for desc in descriptions:
    try:
        results = generate_circuit_from_description(
            desc,
            save_dir=Path("outputs/batch"),
            show=False
        )
        print(f"✓ {results['topology']}")
    except Exception as e:
        print(f"✗ {desc}: {e}")
```

## Performance Tuning

- **Cold Start**: First call loads all models (~5-10s)
- **Warm Cache**: Subsequent calls reuse loaded models
- **Model Size**: Each model ~5-50MB depending on complexity
- **Prediction Time**: ~100-500ms per prediction
- **Visualization Time**: ~1-5s depending on circuit complexity

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No models found | Check `models/models_forward/` and `models/models_backward/` exist |
| Unknown circuit name | Use `list models` or see SUPPORTED_TOPOLOGIES |
| Parameter defaults missing | Check dataset CSV has statistics computed |
| Diagram not generated | Ensure `circuit_making/visualizations/{topology}.py` exists |
| Ollama not responding | Ensure Ollama service running on localhost:11434 |
| Memory errors | Reduce batch size, process one circuit at a time |

## Configuration

Default settings in workflow:
- Model directory: `models/`
- Dataset directory: `datasets/`
- Output directory: `outputs/`
- Temperature: 25°C
- Supply voltage: 5V (digital), circuit-dependent (analog)

Can be overridden by modifying `end_to_end_workflow.py` or implementing config loading.
