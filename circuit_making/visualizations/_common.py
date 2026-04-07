"""Common schematic builders for topology visualizations using schemdraw."""

from __future__ import annotations

from typing import Mapping

import schemdraw
from schemdraw import elements as elm
from schemdraw import logic


def _fmt_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _text_block(title: str, data: Mapping[str, object]) -> str:
    rows = [(k, v) for k, v in data.items() if v not in (None, "")]
    if not rows:
        return f"{title}: none"

    key_width = max(len(str(key)) for key, _ in rows)
    lines = [title]
    for key, value in rows:
        lines.append(f"{str(key):<{key_width}} : {_fmt_value(value)}")
    return "\n".join(lines)


def _pick_value(data: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return _fmt_value(data[key])

    # Fallback: match keys case-insensitively and independent of separators
    # (e.g., Sum vs sum, Next_Q0 vs nextq0).
    def _norm(token: object) -> str:
        return "".join(ch for ch in str(token).lower() if ch.isalnum())

    normalized_data = [(_norm(actual_key), actual_key) for actual_key in data.keys()]
    for wanted_key in keys:
        wanted_norm = _norm(wanted_key)
        for actual_norm, actual_key in normalized_data:
            if actual_norm == wanted_norm and data[actual_key] not in (None, ""):
                return _fmt_value(data[actual_key])
    return ""


def _add_inputs(d: schemdraw.Drawing, inputs: Mapping[str, object], x: float = 8.5, y: float = 3.8) -> None:
    d.add(
        elm.Label().at((x, y)).label(
            _text_block("Inputs", inputs),
            halign="left",
            valign="top",
            font="DejaVu Sans Mono",
            fontsize=10,
        )
    )


def _add_outputs(d: schemdraw.Drawing, outputs: Mapping[str, object], x: float = 8.5, y: float = 2.2) -> None:
    d.add(
        elm.Label().at((x, y)).label(
            _text_block("Predicted Outputs", outputs),
            halign="left",
            valign="top",
            font="DejaVu Sans Mono",
            fontsize=10,
        )
    )


def _add_title(d: schemdraw.Drawing, title: str, x: float = 4.2, y: float = 4.8) -> None:
    d.add(elm.Label().at((x, y)).label(title))



def _start_analog_layout(d: schemdraw.Drawing) -> None:
    # Shift circuit core up/right so it does not hug the lower-left canvas edge.
    d.move(dx=0.8, dy=0.5)


def _new_drawing() -> schemdraw.Drawing:
    d = schemdraw.Drawing(show=False)
    d.config(unit=2.0, fontsize=12, bgcolor="white", margin=0.8)
    return d










def draw_rlc_series_bandpass(inputs: dict, outputs: dict, title: str = "RLC Series Band-Pass") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    def _format_with_unit(raw: str, unit: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            if unit.lower() in normalized:
                return raw
            return f"{raw} {unit}"

        abs_v = abs(val)
        if unit == "ohm":
            if abs_v >= 1e6:
                return f"{val/1e6:.4g} Mohm"
            if abs_v >= 1e3:
                return f"{val/1e3:.4g} kohm"
            return f"{val:.4g} ohm"
        if unit == "H":
            if abs_v >= 1:
                return f"{val:.4g} H"
            if abs_v >= 1e-3:
                return f"{val*1e3:.4g} mH"
            if abs_v >= 1e-6:
                return f"{val*1e6:.4g} uH"
            return f"{val:.4g} H"
        if unit == "F":
            if abs_v >= 1:
                return f"{val:.4g} F"
            if abs_v >= 1e-3:
                return f"{val*1e3:.4g} mF"
            if abs_v >= 1e-6:
                return f"{val*1e6:.4g} uF"
            if abs_v >= 1e-9:
                return f"{val*1e9:.4g} nF"
            return f"{val:.4g} F"
        return f"{val:.4g} {unit}"

    r_val = _format_with_unit(_pick_value(inputs, "R_ohm", "R"), "ohm")
    l_val = _format_with_unit(_pick_value(inputs, "L_h", "L"), "H")
    c_val = _format_with_unit(_pick_value(inputs, "C_f", "C"), "F")

    # Centered reference-like geometry: series L-C on top branch, shunt R on right.
    x_left = 1.2
    x_l_start = 1.8
    y_top = 2.9
    y_bot = 1.1
    x_r_branch = 8.6
    d.move(dx=0.55, dy=0.25)

    # Professional heading similar to approved style.
    _add_title(d, "RLC Circuit", x=4.9, y=5.35)
    d.add(elm.Label().at((4.9, 5.0)).label("(Series Band Pass Filter)", fontsize=11, color="#333333"))
    d.add(elm.Line().at((3.2, 4.83)).to((6.6, 4.83)))

    # Left terminals and return path.
    d.add(elm.Dot(open=True).at((x_left, y_top)))
    d.add(elm.Dot(open=True).at((x_left, y_bot)))
    d.add(elm.Line().at((x_left, y_bot)).to((x_r_branch, y_bot)))

    # Top series branch: L then C.
    d.add(elm.Line().at((x_left, y_top)).to((x_l_start, y_top)))
    ind = d.add(elm.Inductor().at((x_l_start, y_top)).right().length(1.65))
    d.add(elm.Label().at((ind.center.x, ind.center.y + 0.62)).label("L", fontsize=12))
    if l_val:
        d.add(elm.Label().at((ind.center.x, ind.center.y + 0.28)).label(l_val, fontsize=9))

    d.add(elm.Line().at(ind.end).right().length(0.7))
    cap = d.add(elm.Capacitor().at((ind.end.x + 0.7, y_top)).right().length(1.25))
    d.add(elm.Label().at((cap.center.x, cap.center.y + 0.62)).label("C", fontsize=12))
    if c_val:
        d.add(elm.Label().at((cap.center.x, cap.center.y + 0.28)).label(c_val, fontsize=9))

    d.add(elm.Line().at(cap.end).right().length(1.25))
    out_node = d.add(elm.Dot())
    d.add(elm.Line().at(out_node.center).to((x_r_branch, y_top)))

    # Right shunt resistor branch.
    res = d.add(elm.Resistor().at((x_r_branch, y_top)).down().to((x_r_branch, y_bot)))
    d.add(elm.Label().at((res.center.x + 0.58, res.center.y + 0.05)).label("R", fontsize=12, halign="left"))
    if r_val:
        d.add(elm.Label().at((res.center.x + 0.58, res.center.y - 0.35)).label(r_val, fontsize=9, halign="left"))

    # Signal labels with true subscripts and a current-flow arrow.
    d.add(elm.Label().at((x_left + 0.18, 1.95)).label(r"$V_{in}$", halign="left", fontsize=12))
    d.add(elm.Label().at((out_node.center.x, 1.95)).label(r"$V_{out}$", halign="center", fontsize=12))
    # Keep current label and direction arrow separated to avoid overlap.
    d.add(elm.Label().at((3.8, y_top + 0.66)).label(r"$I_{in}$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((3.15, y_top + 0.34)).right().length(0.9))

    # Output node marker on return path like the reference.
    d.add(elm.Dot().at((out_node.center.x, y_bot)))

    return d


def draw_rlc_parallel_bandpass(inputs: dict, outputs: dict, title: str = "RLC Parallel Band-Pass") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    def _format_with_unit(raw: str, unit: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            if unit.lower() in normalized:
                return raw
            return f"{raw} {unit}"

        abs_v = abs(val)
        if unit == "ohm":
            if abs_v >= 1e6:
                return f"{val/1e6:.4g} Mohm"
            if abs_v >= 1e3:
                return f"{val/1e3:.4g} kohm"
            return f"{val:.4g} ohm"
        if unit == "H":
            if abs_v >= 1:
                return f"{val:.4g} H"
            if abs_v >= 1e-3:
                return f"{val*1e3:.4g} mH"
            if abs_v >= 1e-6:
                return f"{val*1e6:.4g} uH"
            return f"{val:.4g} H"
        if unit == "F":
            if abs_v >= 1:
                return f"{val:.4g} F"
            if abs_v >= 1e-3:
                return f"{val*1e3:.4g} mF"
            if abs_v >= 1e-6:
                return f"{val*1e6:.4g} uF"
            if abs_v >= 1e-9:
                return f"{val*1e9:.4g} nF"
            return f"{val:.4g} F"
        return f"{val:.4g} {unit}"

    r_val = _format_with_unit(_pick_value(inputs, "R_ohm", "R"), "ohm")
    l_val = _format_with_unit(_pick_value(inputs, "L_h", "L"), "H")
    c_val = _format_with_unit(_pick_value(inputs, "C_f", "C"), "F")

    # Centered, reference-aligned geometry.
    x_left = 1.25
    x_mid = 3.05
    x_out = 6.15
    x_r = 7.9
    y_top = 3.05
    y_bot = 1.15
    d.move(dx=0.55, dy=0.25)

    # Professional heading consistent with recent approved analog style.
    _add_title(d, "RLC Circuit", x=4.8, y=5.35)
    d.add(elm.Label().at((4.8, 5.0)).label("(Parallel Band Pass Filter)", fontsize=11, color="#333333"))
    d.add(elm.Line().at((3.25, 4.83)).to((6.35, 4.83)))

    # Top and bottom rails with open terminals on the left.
    d.add(elm.Dot(open=True).at((x_left, y_top)))
    d.add(elm.Dot(open=True).at((x_left, y_bot)))
    d.add(elm.Line().at((x_left, y_top)).to((x_r, y_top)))
    d.add(elm.Line().at((x_left, y_bot)).to((x_r, y_bot)))

    # Parallel LC branch between the central top/bottom nodes.
    l_x = x_mid - 0.35
    d.add(elm.Line().at((x_mid, y_top)).to((l_x, y_top)))
    l_elem = d.add(elm.Inductor().at((l_x, y_top)).down().to((l_x, y_bot)))
    d.add(elm.Line().at((l_x, y_bot)).to((x_mid, y_bot)))
    d.add(elm.Label().at((l_x - 0.24, (y_top + y_bot) / 2 + 0.1)).label("L", fontsize=12, halign="right"))
    if l_val:
        # Keep long L-values clear of the inductor by right-aligning text on the left side.
        d.add(elm.Label().at((l_x - 0.52, (y_top + y_bot) / 2 - 0.34)).label(f"L={l_val}", fontsize=8.4, halign="right"))

    c_x = x_mid + 0.9
    d.add(elm.Line().at((x_mid, y_top)).to((c_x, y_top)))
    c_elem = d.add(elm.Capacitor().at((c_x, y_top)).down().to((c_x, y_bot)))
    d.add(elm.Line().at((c_x, y_bot)).to((x_mid, y_bot)))
    d.add(elm.Label().at((c_x + 0.34, (y_top + y_bot) / 2 + 0.08)).label("C", fontsize=12, halign="left"))
    if c_val:
        d.add(elm.Label().at((c_x + 0.36, (y_top + y_bot) / 2 - 0.34)).label(f"C={c_val}", fontsize=8.4, halign="left"))

    # Output tap and right-side shunt resistor branch.
    d.add(elm.Dot().at((x_out, y_top)))
    d.add(elm.Dot().at((x_out, y_bot)))
    r_elem = d.add(elm.Resistor().at((x_r, y_top)).down().to((x_r, y_bot)))
    d.add(elm.Label().at((x_r + 0.48, (y_top + y_bot) / 2 + 0.08)).label("R", fontsize=12, halign="left"))
    if r_val:
        d.add(elm.Label().at((x_r + 0.5, (y_top + y_bot) / 2 - 0.34)).label(f"R={r_val}", fontsize=8.4, halign="left"))

    # Voltage labels and a current-direction arrow near the input rail.
    d.add(elm.Label().at((x_left - 0.32, 2.32)).label(r"$V_{in}$", halign="left", fontsize=12))
    d.add(elm.Label().at((x_out - 0.02, 2.1)).label(r"$V_{out}$", halign="center", fontsize=12))
    d.add(elm.Label().at((2.05, y_top + 0.64)).label(r"$I_{in}$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((1.6, y_top + 0.33)).right().length(0.84))

    return d





def draw_clipper(inputs: dict, outputs: dict, title: str = "Clipper") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)
    d.move(dx=0.9, dy=0.5)

    def _fmt_ohm(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            return raw if "ohm" in normalized else f"{raw} ohm"
        if abs(val) >= 1e6:
            return f"{val/1e6:.4g} Mohm"
        if abs(val) >= 1e3:
            return f"{val/1e3:.4g} kohm"
        return f"{val:.4g} ohm"

    def _fmt_v(raw: str) -> str:
        if not raw:
            return ""
        try:
            return f"{float(raw):.4g} V"
        except ValueError:
            return raw if "v" in raw.lower() else f"{raw} V"

    r1_val = _fmt_ohm(_pick_value(inputs, "R1_ohm", "R_ohm", "R1", "R"))
    vin_val = _fmt_v(_pick_value(inputs, "Vin_V", "Vin", "input_peak_voltage", "vin"))
    vd_val = _fmt_v(_pick_value(inputs, "diode_drop", "Vd", "V_D"))
    vout_val = _fmt_v(_pick_value(outputs, "Vout_V", "Vout", "vout"))

    _add_title(d, "Clipper Circuit", x=5.0, y=5.58)
    d.add(elm.Label().at((5.0, 5.28)).label("Diode Limiter Configuration", fontsize=10, color="#444444"))

    # Reference-aligned geometry.
    x_src = 1.05
    x_r_start = 2.05
    x_node = 4.75
    x_out = 7.7
    y_top = 3.0
    y_bot = 0.5

    src = d.add(elm.SourceSin().at((x_src, y_bot)).up().to((x_src, y_top)))
    d.add(elm.Label().at((x_src + 0.12, y_top - 0.12)).label("+", fontsize=10, halign="center"))
    d.add(elm.Label().at((x_src + 0.12, y_bot + 0.12)).label("-", fontsize=10, halign="center"))
    vin_text = rf"$V_{{in}}$={vin_val}" if vin_val else r"$V_{in}$"
    d.add(elm.Label().at((x_src + 0.42, (y_top + y_bot) / 2)).label(vin_text, halign="left"))

    d.add(elm.Line().at(src.end).to((x_r_start, y_top)))
    r1 = d.add(elm.Resistor().at((x_r_start, y_top)).right().to((x_node, y_top)))
    r1_text = rf"$R_1$={r1_val}" if r1_val else r"$R_1$"
    d.add(elm.Label().at((r1.center.x, r1.center.y + 0.56)).label(r1_text, halign="center"))
    d.add(elm.Label().at((x_r_start + 0.4, y_top + 0.34)).label(r"$I_{in}$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((x_r_start + 0.1, y_top + 0.14)).right().length(0.5))

    d.add(elm.Dot().at((x_node, y_top)))
    d.add(elm.Line().at((x_node, y_top)).to((x_out, y_top)))

    diode = d.add(elm.Diode().at((x_node, y_top)).down().to((x_node, y_bot)))
    diode_text = rf"$D_1$={vd_val}" if vd_val else r"$D_1$"
    d.add(elm.Label().at((x_node - 0.4, diode.center.y + 0.06)).label(diode_text, halign="right"))

    d.add(elm.Line().at(src.start).to((x_out, y_bot)))
    d.add(elm.Dot(open=True).at((x_out, y_top)))
    d.add(elm.Dot(open=True).at((x_out, y_bot)))

    d.add(elm.Arrow().at((x_out + 0.03, y_bot + 0.24)).up().length(0.78))
    d.add(elm.Arrow().at((x_out + 0.03, y_top - 0.24)).down().length(0.78))
    d.add(elm.Label().at((x_out + 0.28, (y_top + y_bot) / 2 + 0.08)).label(r"$V_{out}$", halign="left"))
    if vout_val:
        d.add(elm.Label().at((x_out + 0.28, (y_top + y_bot) / 2 - 0.24)).label(f"={vout_val}", halign="left", fontsize=9))

    return d


def draw_clamper(inputs: dict, outputs: dict, title: str = "Clamper") -> schemdraw.Drawing:
    d = _new_drawing()
    _start_analog_layout(d)
    # Make clamper topology larger and more spacious.
    d.config(unit=3.0)
    vin = _pick_value(inputs, "input_peak_voltage", "Vin", "vin")
    freq = _pick_value(inputs, "frequency", "freq_hz", "Frequency_Hz")
    c_val = _pick_value(inputs, "capacitance", "C", "C_f")
    r_val = _pick_value(inputs, "load_resistance", "R", "RL", "R_load")
    d_drop = _pick_value(inputs, "diode_drop")

    def _si_with_unit(raw: str, unit: str) -> str:
        try:
            value = float(raw)
        except Exception:
            return f"{raw} {unit}" if raw else ""

        abs_v = abs(value)
        if abs_v >= 1e6:
            return f"{value/1e6:.4g} M{unit}"
        if abs_v >= 1e3:
            return f"{value/1e3:.4g} k{unit}"
        if abs_v >= 1:
            return f"{value:.4g} {unit}"
        if abs_v >= 1e-3:
            return f"{value*1e3:.4g} m{unit}"
        if abs_v >= 1e-6:
            return f"{value*1e6:.4g} u{unit}"
        return f"{value:.4g} {unit}"

    c_label = _si_with_unit(c_val, "F") if c_val else ""
    r_label = _si_with_unit(r_val, "ohm") if r_val else ""
    d_label = f"D ({d_drop} V)" if d_drop else "D"

    freq_label = _si_with_unit(freq, "Hz") if freq else ""

    if vin and freq_label:
        src_label = f"Vi={vin} V\nf={freq_label}"
    elif vin:
        src_label = f"Vi={vin} V"
    elif freq_label:
        src_label = f"f={freq_label}"
    else:
        src_label = "Vi"

    src = d.add(elm.SourceSin().at((0.0, 0.0)).up().length(2.4).label(src_label, loc="left"))

    cap = d.add(elm.Capacitor().at(src.end).right().length(2.6).label(c_label, loc="top"))
    top_node = d.add(elm.Dot().at(cap.end))

    # R branch from output node to return path (right side).
    d.add(elm.Line().at(top_node.center).right().length(1.4))
    r_top = (top_node.center.x + 1.4, top_node.center.y)
    r_elem = d.add(elm.Resistor().at(r_top).down().length(2.4))
    if r_label:
        d.add(
            elm.Label().at((r_elem.center.x + 0.65, r_elem.center.y + 0.02)).label(
                r_label,
                halign="left",
                valign="center",
                fontsize=11,
            )
        )
    bottom_node = d.add(elm.Dot().at(r_elem.end))

    # Diode branch in parallel with R branch (classic clamper topology).
    diode = d.add(elm.Diode().at(top_node.center).down().length(2.4))
    d.add(elm.Label().at((diode.center.x - 1.05, diode.center.y + 0.62)).label(d_label, fontsize=11))

    d.add(elm.Line().at(diode.end).to(bottom_node.center))
    d.add(elm.Line().at(bottom_node.center).to(src.start))
    d.add(elm.Label().at((r_top[0] + 0.46, r_top[1] + 0.56)).label("Vo", halign="left"))

    _add_title(d, title, x=4.4)
    panel_inputs = {
        "input_peak_voltage": inputs.get("input_peak_voltage"),
        "frequency": inputs.get("frequency"),
        "capacitance": inputs.get("capacitance"),
        "load_resistance": inputs.get("load_resistance"),
        "diode_drop": inputs.get("diode_drop"),
        "clamper_type": inputs.get("clamper_type"),
    }
    _add_side_panel(d, panel_inputs, outputs, x=10.2, inputs_y=4.8, outputs_y=1.9)
    return d


def draw_opamp_family(inputs: dict, outputs: dict, title: str) -> schemdraw.Drawing:
    d = _new_drawing()
    d.add(elm.Opamp().anchor("in1").label("U1", loc="top"))
    d.add(elm.Line().left().length(1.2).at((-1.8, 0.6)).label("Vin", loc="top"))
    d.add(elm.Resistor().left().at((-1.8, 0.6)).label(_pick_value(inputs, "Rin", "R1"), loc="top"))
    d.add(elm.Line().at((1.8, 0.0)).right().length(1.6).label("Vout", loc="top"))
    d.add(elm.Resistor().down().at((0.8, 0.0)).label(_pick_value(inputs, "Rf", "R2"), loc="right"))
    d.add(elm.Ground())
    _add_title(d, title, x=4.0, y=4.5)
    _add_side_panel(d, inputs, outputs, x=8.8)
    return d


def draw_counter(inputs: dict, outputs: dict, title: str) -> schemdraw.Drawing:
    """Draw a MOD-N counter with cascaded flip-flops and reset logic."""
    d = _new_drawing()
    
    # Get parameters
    num_bits = int(_pick_value(inputs, "num_bits", "bits") or "3")
    mod_value = _pick_value(inputs, "mod_n", "modulo") or f"MOD-{2**num_bits}"
    
    # Main title
    d.add(elm.Label().at((3.0, 5.2)).label("MOD-N Counter", fontsize=16))
    
    # Configuration
    ff_width = 1.2
    ff_height = 1.0
    spacing = 2.2
    start_x = 0.5
    start_y = 3.0
    
    ff_positions = []
    
    # Clock input from top
    clock_y_top = 4.2
    d.add(elm.Line().at((start_x + ff_width/2, clock_y_top)).down().length(0.8))
    d.add(elm.Label().at((start_x + ff_width/2 - 0.4, clock_y_top + 0.2)).label("Clock", fontsize=10))
    
    # Draw all flip-flops
    for i in range(num_bits):
        x = start_x + i * spacing
        y = start_y
        ff_positions.append((x, y))
        
        # Draw FF block
        d.add(elm.Rect(w=ff_width, h=ff_height).at((x, y)))
        
        # FF label
        d.add(elm.Label().at((x, y + 0.1)).label(f"FF{i}", fontsize=10))
        
        # Q output label on right
        d.add(elm.Label().at((x + 0.7, y)).label("Q", fontsize=9))
        
        # Q value below FF
        d.add(elm.Label().at((x, y - 0.65)).label(f"Q{i}", fontsize=9, loc='center'))
        
        # Clock connection to this FF (vertical line from top clock)
        if i == 0:
            # First FF gets direct clock connection
            d.add(elm.Line().at((x, y + ff_height/2 + 0.05)).up().length(0.2))
        else:
            # Other FFs get clock from previous FF's Q output (cascade feedback)
            prev_x = ff_positions[i-1][0]
            d.add(elm.Line().at((prev_x + ff_width/2, y + ff_height/2 + 0.05)).right().length(spacing - ff_width))
    
    # Q outputs on the right (vertical line showing outputs)
    output_x = start_x + (num_bits - 1) * spacing + 1.2
    d.add(elm.Line().at((output_x, start_y + 0.4)).down().length(num_bits * 0.3))
    
    for i in range(num_bits):
        y_out = start_y + 0.4 - i * 0.3
        d.add(elm.Label().at((output_x + 0.4, y_out)).label(f"Q{i}", fontsize=8))
    
    # Bottom section - Reset Logic
    reset_logic_y = 0.5
    
    # Reset logic box
    logic_width = 1.8
    logic_height = 0.8
    logic_x = start_x + (num_bits - 1) * spacing / 2 + 0.3
    
    d.add(elm.Rect(w=logic_width, h=logic_height).at((logic_x, reset_logic_y)))
    d.add(elm.Label().at((logic_x, reset_logic_y + 0.15)).label("Reset Logic", fontsize=9))
    d.add(elm.Label().at((logic_x, reset_logic_y - 0.2)).label(f"Detect {mod_value}", fontsize=8))
    
    # Connection from FFs to reset logic (Q inputs going down)
    for i in range(num_bits):
        x_ff = ff_positions[i][0]
        d.add(elm.Line().at((x_ff + ff_width/2, start_y - ff_height/2 - 0.05)).down()
              .length(start_y - reset_logic_y - logic_height/2 - 0.2))
    
    # RST output from reset logic going back up to FFs
    d.add(elm.Line().at((logic_x, reset_logic_y + logic_height/2 + 0.05)).up()
          .length(start_y - reset_logic_y - logic_height))
    d.add(elm.Label().at((logic_x + 0.8, (start_y + reset_logic_y) / 2)).label("RST", fontsize=8))
    
    # Add inputs/outputs panel
    _add_side_panel(d, inputs, outputs, x=7.5, inputs_y=4.0, outputs_y=2.0)
    
    return d

def draw_log_amplifier(
    inputs: dict,
    outputs: dict,
    title: str = "Log Amplifier",
    swap_resistor_diode: bool = False,
) -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)
    d.move(dx=0.85, dy=0.3)

    def _fmt_ohm(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            return raw if "ohm" in normalized else f"{raw} ohm"
        if abs(val) >= 1e6:
            return f"{val/1e6:.4g} Mohm"
        if abs(val) >= 1e3:
            return f"{val/1e3:.4g} kohm"
        return f"{val:.4g} ohm"

    def _fmt_v(raw: str) -> str:
        if not raw:
            return ""
        try:
            return f"{float(raw):.4g} V"
        except ValueError:
            return raw if "v" in raw.lower() else f"{raw} V"

    r1_val = _fmt_ohm(_pick_value(inputs, "R1_ohm", "Rin_ohm", "R1", "Rin", "R"))
    vd_val = _fmt_v(_pick_value(inputs, "diode_drop", "Vd", "V_D"))
    vin_val = _fmt_v(_pick_value(inputs, "Vin_V", "Vin", "vin"))
    vout_val = _fmt_v(_pick_value(outputs, "Vout_V", "Vout", "vout"))

    heading = f"{title} Circuit" if "circuit" not in title.lower() else title
    _add_title(d, heading, x=5.1, y=5.65)
    d.add(elm.Label().at((5.1, 5.35)).label("Op-Amp Analog Configuration", fontsize=10, color="#444444"))

    op = d.add(elm.Opamp().at((5.65, 2.35)).label("A", loc="center"))

    vin_node = (1.0, op.in1.y)
    d.add(elm.Dot().at(vin_node))
    vin_text = rf"$V_{{i}}$={vin_val}" if vin_val else r"$V_i$"
    d.add(elm.Label().at((0.68, op.in1.y)).label(vin_text, halign="right"))
    r1_start = (1.85, op.in1.y)
    sum_node_xy = (op.in1.x - 0.95, op.in1.y)
    d.add(elm.Line().at(vin_node).to(r1_start))
    if swap_resistor_diode:
        in_elem = d.add(elm.Diode().at(r1_start).right().to(sum_node_xy))
        d.add(elm.Label().at((in_elem.center.x, in_elem.center.y + 0.62)).label("D", halign="center"))
        if vd_val:
            d.add(elm.Label().at((in_elem.center.x, in_elem.center.y + 0.34)).label(f"={vd_val}", halign="center", fontsize=9))
    else:
        r1 = d.add(elm.Resistor().at(r1_start).right().to(sum_node_xy))
        in_elem = r1
        r1_text = rf"$R_1$={r1_val}" if r1_val else r"$R_1$"
        d.add(elm.Label().at((r1.center.x, r1.center.y + 0.62)).label(r1_text, halign="center"))
    d.add(elm.Label().at((in_elem.center.x - 0.68, in_elem.center.y - 0.56)).label(r"$I_{in}$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((in_elem.center.x - 0.98, in_elem.center.y - 0.76)).right().length(0.52))

    sum_node = d.add(elm.Dot().at(sum_node_xy))
    d.add(elm.Line().at(sum_node.center).to(op.in1))

    top_y = 3.92
    d.add(elm.Line().at(sum_node.center).up().to((sum_node.center.x, top_y)))
    if swap_resistor_diode:
        fb_elem = d.add(elm.Resistor().at((sum_node.center.x, top_y)).right().to((op.out.x, top_y)))
        r1_text = rf"$R_1$={r1_val}" if r1_val else r"$R_1$"
        d.add(elm.Label().at((fb_elem.center.x, fb_elem.center.y + 0.62)).label(r1_text, halign="center"))
    else:
        fb_elem = d.add(elm.Diode().at((sum_node.center.x, top_y)).right().to((op.out.x, top_y)))
        d.add(elm.Label().at((fb_elem.center.x, fb_elem.center.y + 0.65)).label("D", halign="center"))
        if vd_val:
            d.add(elm.Label().at((fb_elem.center.x, fb_elem.center.y + 0.35)).label(f"={vd_val}", halign="center", fontsize=9))
    d.add(elm.Label().at((fb_elem.center.x + 0.46, fb_elem.center.y - 0.5)).label(r"$I_f$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((fb_elem.center.x + 0.16, fb_elem.center.y - 0.68)).right().length(0.5))
    d.add(elm.Line().at((op.out.x, top_y)).down().to(op.out))

    ground_drop = (op.in2.x, op.in2.y - 0.62)
    d.add(elm.Line().at(op.in2).down().to(ground_drop))
    d.add(elm.Line().at(ground_drop).left().length(0.5))
    d.add(elm.Ground())

    d.add(elm.Line().at(op.out).right().length(1.8))
    out_dot = d.add(elm.Dot())
    vout_text = rf"$V_{{o}}$={vout_val}" if vout_val else r"$V_o$"
    d.add(elm.Label().at((out_dot.center.x + 0.24, out_dot.center.y)).label(vout_text, halign="left"))

    return d


def draw_voltage_follower(inputs: dict, outputs: dict, title: str = "Voltage Follower") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)
    d.move(dx=0.8, dy=0.3)

    def _fmt_ohm(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            return raw if "ohm" in normalized else f"{raw} ohm"
        if abs(val) >= 1e6:
            return f"{val/1e6:.4g} Mohm"
        if abs(val) >= 1e3:
            return f"{val/1e3:.4g} kohm"
        return f"{val:.4g} ohm"

    def _fmt_v(raw: str) -> str:
        if not raw:
            return ""
        try:
            return f"{float(raw):.4g} V"
        except ValueError:
            return raw if "v" in raw.lower() else f"{raw} V"

    r_top = _fmt_ohm(_pick_value(inputs, "R1_ohm", "R_top_ohm", "R1", "R_top", "R"))
    r_bot = _fmt_ohm(_pick_value(inputs, "R2_ohm", "R_bottom_ohm", "R2", "R_bot", "R_bottom"))
    vcc = _fmt_v(_pick_value(inputs, "Vcc_V", "VCC_V", "Vcc", "VCC"))
    vref = _fmt_v(_pick_value(outputs, "Vref_V", "Vref", "VREF", "Vout_V", "Vout"))

    _add_title(d, "Voltage Follower Circuit", x=5.05, y=5.72)
    d.add(elm.Label().at((5.05, 5.42)).label("Op-Amp Analog Configuration", fontsize=10, color="#444444"))

    # Op-amp follower core.
    op = d.add(elm.Opamp().right().flip().at((5.1, 2.52)))

    # Left divider: VCC -> R1 -> midpoint -> R2 -> GND.
    # Keep midpoint on same y-level as '+' input so the interconnect is straight.
    x_div = 1.55
    y_mid = op.in2.y
    y_vcc = y_mid + 1.6
    y_gnd = y_mid - 1.6

    d.add(elm.Dot(open=True).at((x_div, y_vcc)))
    d.add(elm.Label().at((x_div + 0.05, y_vcc + 0.3)).label(r"$V_{CC}$", halign="center"))
    if vcc:
        d.add(elm.Label().at((x_div + 0.62, y_vcc + 0.3)).label(f"={vcc}", halign="left", fontsize=9))

    top_res = d.add(elm.Resistor().at((x_div, y_vcc)).down().to((x_div, y_mid)))
    top_text = rf"$R_1$={r_top}" if r_top else r"$R_1$"
    d.add(elm.Label().at((x_div - 0.38, top_res.center.y + 0.02)).label(top_text, halign="right"))

    mid_node = d.add(elm.Dot().at((x_div, y_mid)))
    bot_res = d.add(elm.Resistor().at((x_div, y_mid)).down().to((x_div, y_gnd)))
    bot_text = rf"$R_2$={r_bot}" if r_bot else r"$R_2$"
    d.add(elm.Label().at((x_div - 0.38, bot_res.center.y - 0.02)).label(bot_text, halign="right"))
    d.add(elm.Ground().at((x_div, y_gnd)))

    # Divider current arrow.
    d.add(elm.Label().at((x_div - 0.24, top_res.center.y + 0.54)).label(r"$I_{in}$", halign="right", fontsize=10))
    d.add(elm.Arrow().at((x_div - 0.22, top_res.center.y + 0.34)).down().length(0.42))

    d.add(elm.Line().at(mid_node.center).to(op.in2))

    d.add(elm.Line().at(op.out).right().length(1.58))
    out_node = d.add(elm.Dot(open=True))
    vref_text = rf"$V_{{REF}}$={vref}" if vref else r"$V_{REF}$"
    d.add(elm.Label().at((out_node.center.x + 0.27, out_node.center.y)).label(vref_text, halign="left"))

    fb_y = op.in1.y - 0.72
    fb_left_x = op.in1.x - 0.04
    d.add(elm.Line().at(op.out).down().to((op.out.x, fb_y)))
    d.add(elm.Line().at((op.out.x, fb_y)).left().to((fb_left_x, fb_y)))
    d.add(elm.Line().at((fb_left_x, fb_y)).up().to(op.in1))
    d.add(elm.Label().at((op.in1.x + 0.34, fb_y - 0.22)).label(r"$I_f$", halign="left", fontsize=10))
    d.add(elm.Arrow().at((op.in1.x + 0.16, fb_y - 0.4)).right().length(0.43))

    return d


def draw_inverting(inputs: dict, outputs: dict, title: str = "Inverting Amplifier") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)
    d.move(dx=0.95, dy=0.35)

    def _fmt_ohm(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            return raw if "ohm" in normalized else f"{raw} ohm"

        abs_v = abs(val)
        if abs_v >= 1e6:
            return f"{val/1e6:.4g} Mohm"
        if abs_v >= 1e3:
            return f"{val/1e3:.4g} kohm"
        return f"{val:.4g} ohm"

    rin_val = _fmt_ohm(_pick_value(inputs, "Rin_ohm", "Rin", "R1"))
    rf_val = _fmt_ohm(_pick_value(inputs, "Rf_ohm", "Rf", "R2"))
    vin_val = _pick_value(inputs, "Vin_V", "Vin", "vin")
    vout_val = _pick_value(outputs, "Vout_V", "Vout", "vout")

    # Heading, centered and professional.
    _add_title(d, "Inverting Amplifier Circuit", x=4.95, y=5.7)
    d.add(elm.Label().at((4.95, 5.38)).label("Op-Amp Analog Configuration", fontsize=10, color="#444444"))

    # Op-amp triangle shifted right so the summing node sits outside the body,
    # matching the reference-style feedback loop geometry.
    op = d.add(elm.Opamp().at((5.95, 2.4)).label("A", loc="center"))

    # Input path: Vin -> Rin -> inverting node.
    vin_node = (1.05, op.in1.y)
    d.add(elm.Dot().at(vin_node))
    vin_label = rf"$V_{{in}}$={vin_val} V" if vin_val else r"$V_{in}$"
    d.add(elm.Label().at((0.7, op.in1.y)).label(vin_label, halign="right"))
    rin_start = (2.0, op.in1.y)
    d.add(elm.Line().at(vin_node).to(rin_start))
    sum_node_xy = (op.in1.x - 0.46, op.in1.y)
    rin = d.add(elm.Resistor().at(rin_start).right().to(sum_node_xy))
    rin_label = rf"$R_{{in}}$={rin_val}" if rin_val else r"$R_{in}$"
    d.add(elm.Label().at((rin.center.x, rin.center.y + 0.64)).label(rin_label, halign="center"))
    d.add(elm.Label().at((rin.center.x - 0.72, rin.center.y - 0.58)).label(r"$I_{in}$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((rin.center.x - 1.0, rin.center.y - 0.78)).right().length(0.56))

    sum_node = d.add(elm.Dot().at(sum_node_xy))
    d.add(elm.Line().at(sum_node.center).to(op.in1))

    # Feedback path on top: output -> Rf -> inverting node.
    top_y = 3.88
    d.add(elm.Line().at(sum_node.center).up().to((sum_node.center.x, top_y)))
    rf = d.add(elm.Resistor().at((sum_node.center.x, top_y)).right().to((op.out.x, top_y)))
    d.add(elm.Label().at((rf.center.x, rf.center.y + 0.8)).label(r"$R_f$", halign="center"))
    if rf_val:
        d.add(elm.Label().at((rf.center.x, rf.center.y + 0.5)).label(f"={rf_val}", halign="center", fontsize=9))
    d.add(elm.Line().at((op.out.x, top_y)).down().to(op.out))

    # Non-inverting input grounded.
    d.add(elm.Line().at(op.in2).down().length(1.35))
    d.add(elm.Ground())

    # Output path.
    d.add(elm.Line().at(op.out).right().length(1.9))
    out_dot = d.add(elm.Dot())
    vout_label = rf"$V_{{out}}$={vout_val} V" if vout_val else r"$V_{out}$"
    d.add(elm.Label().at((out_dot.center.x + 0.28, out_dot.center.y)).label(vout_label, halign="left"))

    return d


def draw_differentiator(inputs: dict, outputs: dict, title: str = "Differentiator") -> schemdraw.Drawing:
    d = _new_drawing()
    _start_analog_layout(d)
    d.config(unit=2.6)
    # Shift right slightly so the standalone circuit (without side panel)
    # sits more centrally in the rendered canvas.
    d.move(dx=1.2, dy=0.0)

    c_val = _pick_value(inputs, "C", "capacitance", "C_f")
    rf_val = _pick_value(inputs, "Rf", "R", "feedback_resistance", "R_ohm")

    def _fmt_with_unit(value: str, unit: str) -> str:
        if not value:
            return ""
        try:
            numeric = float(value)
        except ValueError:
            normalized = value.lower().replace(" ", "")
            if unit == "ohm" and "ohm" in normalized:
                return value
            if unit == "F" and normalized.endswith("f"):
                return value
            return f"{value} {unit}"

        abs_v = abs(numeric)
        if unit == "ohm":
            if abs_v >= 1e6:
                return f"{numeric/1e6:.4g} Mohm"
            if abs_v >= 1e3:
                return f"{numeric/1e3:.4g} kohm"
            return f"{numeric:.4g} ohm"
        if unit == "F":
            if abs_v >= 1:
                return f"{numeric:.4g} F"
            if abs_v >= 1e-3:
                return f"{numeric*1e3:.4g} mF"
            if abs_v >= 1e-6:
                return f"{numeric*1e6:.4g} uF"
            if abs_v >= 1e-9:
                return f"{numeric*1e9:.4g} nF"
            return f"{numeric:.4g} F"
        return f"{numeric:.4g} {unit}"

    c_label_value = _fmt_with_unit(c_val, "F")
    rf_label_value = _fmt_with_unit(rf_val, "ohm")

    # Use default op-amp orientation so '-' is upper input and '+' is lower input.
    op = d.add(elm.Opamp().at((5.5, 1.8)).label("A", loc="center"))

    # Vin node at left with return to ground, then capacitor into summing node.
    vin_node = (0.9, op.in1.y)
    d.add(elm.Dot().at(vin_node))
    d.add(elm.Label().at((0.55, op.in1.y)).label("Vin", halign="right"))
    d.add(elm.Line().at(vin_node).down().length(1.8))
    d.add(elm.Ground())

    cap_start = (2.0, op.in1.y)
    d.add(elm.Line().at(vin_node).to(cap_start))
    d.add(elm.Label().at((1.45, op.in1.y + 0.42)).label(r"$I_{in}$", halign="center"))
    d.add(elm.Arrow().at((1.05, op.in1.y + 0.22)).right().length(0.8))
    cap = d.add(elm.Capacitor().at(cap_start).right().length(1.2))
    if c_label_value:
        d.add(elm.Label().at((cap.center.x, cap.center.y + 0.52)).label(c_label_value, halign="center"))
    d.add(elm.Label().at((cap.center.x, cap.center.y - 0.58)).label(r"$V_c$", halign="center"))

    sum_node = d.add(elm.Dot().at(cap.end))
    d.add(elm.Line().at(sum_node.center).to(op.in1))

    # Feedback resistor from output to summing node via top path.
    top_y = 3.55
    d.add(elm.Line().at(sum_node.center).up().to((sum_node.center.x, top_y)))
    fb = d.add(elm.Resistor().at((sum_node.center.x, top_y)).right().to((op.out.x, top_y)))
    d.add(elm.Label().at((fb.center.x, fb.center.y + 1.02)).label(r"$R_f$", halign="center"))
    if rf_label_value:
        d.add(elm.Label().at((fb.center.x, fb.center.y + 0.58)).label(rf_label_value, halign="center", fontsize=10))
    d.add(elm.Label().at((fb.center.x - 1.28, fb.center.y + 0.15)).label(r"$I_f$", halign="center"))
    d.add(elm.Arrow().at((fb.center.x - 1.74, fb.center.y - 0.05)).right().length(0.88))
    d.add(elm.Line().at((op.out.x, top_y)).down().to(op.out))

    # Non-inverting input grounded.
    d.add(elm.Line().at(op.in2).down().length(1.35))
    d.add(elm.Ground())

    # Output node and ground reference marker like the reference image.
    d.add(elm.Line().at(op.out).right().length(1.9))
    vout_dot = d.add(elm.Dot())
    d.add(elm.Label().at((vout_dot.center.x + 0.28, vout_dot.center.y)).label(r"$V_{out}$", halign="left"))
    d.add(elm.Line().at(vout_dot.center).down().length(1.8))
    d.add(elm.Ground())

    _add_title(d, f"{title} Circuit", x=4.9, y=5.7)
    d.add(elm.Label().at((4.9, 5.35)).label("Op-Amp Analog Configuration", fontsize=10, color="#444444"))
    return d





def draw_bjt_family(inputs: dict, outputs: dict, title: str) -> schemdraw.Drawing:
    d = _new_drawing()
    d.add(elm.BjtNpn(circle=True).label("Q1", loc="right"))
    d.add(elm.Resistor().up().at((0.8, 1.2)).label(_pick_value(inputs, "RC"), loc="right"))
    d.add(elm.Line().up().length(0.7))
    d.add(elm.Dot().label("VCC", loc="top"))
    d.add(elm.Resistor().down().at((0.8, -1.2)).label(_pick_value(inputs, "RE"), loc="right"))
    d.add(elm.Ground())
    d.add(elm.Resistor().left().at((-1.2, 0.0)).label(_pick_value(inputs, "RB"), loc="top"))
    d.add(elm.SourceSin().left().label("Vin", loc="bottom"))
    d.add(elm.Line().right().at((0.8, 1.9)).length(1.8).label("Vout", loc="top"))
    _add_title(d, title, x=4.0, y=4.5)
    _add_side_panel(d, inputs, outputs, x=8.9)
    return d


def draw_bjt_ce(inputs: dict, outputs: dict, title: str = "BJT Common-Emitter") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)
    d.move(dx=0.7, dy=0.25)

    def _pick_param(*keys: str) -> str:
        value = _pick_value(inputs, *keys)
        if value:
            return value
        return _pick_value(outputs, *keys)

    def _fmt_res(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            return raw if "ohm" in normalized else f"{raw} ohm"
        abs_v = abs(val)
        if abs_v >= 1e6:
            return f"{val/1e6:.4g} Mohm"
        if abs_v >= 1e3:
            return f"{val/1e3:.4g} kohm"
        return f"{val:.4g} ohm"

    def _fmt_cap(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            if normalized.endswith("f"):
                return raw
            return f"{raw} F"
        abs_v = abs(val)
        if abs_v >= 1e-3:
            return f"{val*1e3:.4g} mF"
        if abs_v >= 1e-6:
            return f"{val*1e6:.4g} uF"
        if abs_v >= 1e-9:
            return f"{val*1e9:.4g} nF"
        return f"{val:.4g} F"

    def _fmt_v(raw: str) -> str:
        if not raw:
            return ""
        try:
            return f"{float(raw):.4g} V"
        except ValueError:
            return raw if "v" in raw.lower() else f"{raw} V"

    rb1_val = _fmt_res(_pick_param("Rb1_ohm", "RB1_ohm", "Rb1", "RB1", "RB"))
    rb2_val = _fmt_res(_pick_param("Rb2_ohm", "RB2_ohm", "Rb2", "RB2"))
    rc_val = _fmt_res(_pick_param("Rc_ohm", "RC_ohm", "Rc", "RC"))
    re_val = _fmt_res(_pick_param("Re_ohm", "RE_ohm", "Re", "RE"))
    rl_val = _fmt_res(_pick_param("Rl_ohm", "RL_ohm", "Rl", "RL", "R_load"))
    vcc_val = _fmt_v(_pick_param("Vcc_V", "VCC_V", "Vcc", "VCC"))
    vin_val = _fmt_v(_pick_param("Vin_V", "VIN_V", "Vin", "VIN", "vin"))
    vout_val = _fmt_v(_pick_param("Vout_V", "VOUT_V", "Vout", "VOUT", "vout"))

    _add_title(d, "BJT Common-Emitter Circuit", x=5.35, y=6.05)
    d.add(elm.Label().at((5.35, 5.74)).label("Analog Transistor Configuration", fontsize=10, color="#444444"))

    q = d.add(elm.BjtNpn(circle=True).at((5.45, 2.2)))
    d.add(elm.Label().at((q.base.x - 0.2, q.base.y + 0.14)).label("B", halign="right"))
    d.add(elm.Label().at((q.collector.x + 0.12, q.collector.y + 0.18)).label("C", halign="left"))
    d.add(elm.Label().at((q.emitter.x + 0.14, q.emitter.y - 0.08)).label("E", halign="left"))

    y_vcc = 5.0
    y_out = q.collector.y + 0.9
    y_vin = q.base.y - 1.32
    y_gnd = 0.72
    x_left = 2.25
    x_right = 8.08

    # Top rail and VCC node.
    d.add(elm.Line().at((q.collector.x, y_vcc)).to((x_right, y_vcc)))
    d.add(elm.Dot().at((q.collector.x, y_vcc)))
    d.add(elm.Label().at((q.collector.x, y_vcc + 0.32)).label(r"$V_{CC}$", halign="center"))
    if vcc_val:
        d.add(elm.Label().at((q.collector.x + 0.56, y_vcc + 0.3)).label(f"={vcc_val}", halign="left", fontsize=9))

    # RC branch from VCC to output/collector node.
    rc = d.add(elm.Resistor().at((q.collector.x, y_vcc)).down().to((q.collector.x, y_out)))
    rc_label = rf"$R_C$={rc_val}" if rc_val else r"$R_C$"
    d.add(elm.Label().at((rc.center.x - 0.44, rc.center.y + 0.02)).label(rc_label, halign="right"))
    d.add(elm.Label().at((rc.center.x - 0.38, rc.center.y + 0.58)).label(r"$I_C$", halign="right", fontsize=10))
    d.add(elm.Arrow().at((rc.center.x - 0.38, rc.center.y + 0.4)).down().length(0.38))

    # Top-right RL branch from VCC to same output node.
    rl_top = d.add(elm.Resistor().at((x_right, y_vcc)).down().to((x_right, y_out)))
    rl_top_label = rf"$R_L$={rl_val}" if rl_val else r"$R_L$"
    d.add(elm.Label().at((rl_top.center.x + 0.22, rl_top.center.y + 0.72)).label(rl_top_label, halign="left"))

    # Output/collector bus and Vout node.
    d.add(elm.Line().at((x_left, y_out)).to((x_right + 0.44, y_out)))
    d.add(elm.Dot().at((q.collector.x, y_out)))
    d.add(elm.Dot().at((x_right, y_out)))
    vout_node = d.add(elm.Dot(open=True).at((x_right + 0.44, y_out)))
    vout_text = rf"$V_{{out}}$={vout_val}" if vout_val else r"$V_{out}$"
    d.add(elm.Label().at((vout_node.center.x + 0.62, y_out + 0.02)).label(vout_text, halign="left"))

    # Collector pin to collector bus.
    d.add(elm.Line().at(q.collector).up().to((q.collector.x, y_out)))

    # Left RB1-RB2 network with Vin node at the bottom.
    rb1 = d.add(elm.Resistor().at((x_left, y_out)).down().to((x_left, q.base.y)))
    rb1_label = rf"$R_{{B1}}$={rb1_val}" if rb1_val else r"$R_{B1}$"
    d.add(elm.Label().at((rb1.center.x - 0.26, rb1.center.y + 0.04)).label(rb1_label, halign="right"))

    rb2 = d.add(elm.Resistor().at((x_left, q.base.y)).down().to((x_left, y_vin)))
    rb2_label = rf"$R_{{B2}}$={rb2_val}" if rb2_val else r"$R_{B2}$"
    d.add(elm.Label().at((rb2.center.x - 0.62, rb2.center.y + 0.38)).label(rb2_label, halign="right"))
    d.add(elm.Dot().at((x_left, q.base.y)))

    # Base connection from divider node.
    d.add(elm.Line().at((x_left, q.base.y)).to(q.base))
    d.add(elm.Label().at((q.base.x - 1.04, q.base.y - 0.86)).label(r"$I_B$", halign="center", fontsize=10))
    d.add(elm.Arrow().at((q.base.x - 1.3, q.base.y - 1.06)).right().length(0.46))

    # Vin open node as in reference.
    vin_node = d.add(elm.Dot(open=True).at((x_left, y_vin)))
    vin_text = rf"$V_{{in}}$={vin_val}" if vin_val else r"$V_{in}$"
    d.add(elm.Label().at((vin_node.center.x - 0.56, vin_node.center.y - 0.08)).label(vin_text, halign="right"))

    # Right lower RL branch from output node down to emitter level.
    rl_side = d.add(elm.Resistor().at((x_right, y_out)).down().to((x_right, q.emitter.y)))
    rl_side_label = rf"$R_L$={rl_val}" if rl_val else r"$R_L$"
    d.add(elm.Label().at((rl_side.center.x + 0.42, rl_side.center.y - 0.02)).label(rl_side_label, halign="left"))
    d.add(elm.Line().at((x_right, q.emitter.y)).to((q.emitter.x, q.emitter.y)))

    # Emitter resistor to ground.
    re = d.add(elm.Resistor().at(q.emitter).down().to((q.emitter.x, y_gnd + 0.34)))
    re_label = rf"$R_E$={re_val}" if re_val else r"$R_E$"
    d.add(elm.Label().at((re.center.x + 0.48, re.center.y)).label(re_label, halign="left"))
    d.add(elm.Line().at((q.emitter.x, y_gnd + 0.34)).down().to((q.emitter.x, y_gnd + 0.06)))
    d.add(elm.Ground().at((q.emitter.x, y_gnd + 0.06)))
    d.add(elm.Label().at((q.emitter.x - 0.3, re.center.y + 0.2)).label(r"$I_E$", halign="right", fontsize=10))
    d.add(elm.Arrow().at((q.emitter.x - 0.29, re.center.y + 0.02)).down().length(0.42))

    return d


def draw_bjt_cc(inputs: dict, outputs: dict, title: str = "BJT Common-Collector") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    def _pick_param(*keys: str) -> str:
        # Prefer explicit input values; if absent, fall back to model outputs.
        value = _pick_value(inputs, *keys)
        if value:
            return value
        return _pick_value(outputs, *keys)

    def _fmt_res(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            if "ohm" in normalized:
                return raw
            return f"{raw} ohm"
        abs_v = abs(val)
        if abs_v >= 1e6:
            return f"{val/1e6:.4g} Mohm"
        if abs_v >= 1e3:
            return f"{val/1e3:.4g} kohm"
        return f"{val:.4g} ohm"

    def _fmt_cap(raw: str) -> str:
        if not raw:
            return ""
        try:
            val = float(raw)
        except ValueError:
            normalized = raw.lower().replace(" ", "")
            if normalized.endswith("f"):
                return raw
            return f"{raw} F"
        abs_v = abs(val)
        if abs_v >= 1e-3:
            return f"{val*1e3:.4g} mF"
        if abs_v >= 1e-6:
            return f"{val*1e6:.4g} uF"
        if abs_v >= 1e-9:
            return f"{val*1e9:.4g} nF"
        return f"{val:.4g} F"

    def _fmt_v(raw: str) -> str:
        if not raw:
            return ""
        try:
            return f"{float(raw):.4g} V"
        except ValueError:
            return raw if "v" in raw.lower() else f"{raw} V"

    rc_val = _fmt_res(_pick_param("Rc", "RC"))
    rb1_val = _fmt_res(_pick_param("Rb1", "RB1", "Rb", "RB"))
    rb2_val = _fmt_res(_pick_param("Rb2", "RB2"))
    re_val = _fmt_res(_pick_param("Re", "RE"))
    rl_val = _fmt_res(_pick_param("RL", "Rl", "R_load"))
    cin_val = _fmt_cap(_pick_param("Cin", "C_in", "C", "C_f"))
    vcc_val = _fmt_v(_pick_param("Vcc", "VCC"))

    # Reference-style layout: clean symbol labels only (no numeric clutter).
    d.move(dx=0.85, dy=0.35)
    _add_title(d, "BJT Common-Collector Circuit", x=5.4, y=6.0)
    d.add(elm.Label().at((5.4, 5.7)).label("Emitter Follower Configuration", fontsize=10, color="#444444"))

    # Place transistor first and wire around anchors to avoid distorted links.
    q = d.add(elm.BjtNpn(circle=True).at((5.55, 2.6)).label("Q1", loc="right"))

    x_col = q.collector.x
    y_col = 4.0
    y_vcc = 5.2
    x_bias = 3.15
    y_bias = q.base.y
    y_in = 1.45
    y_gnd = 0.72

    # Supply and collector resistor.
    d.add(elm.Dot(open=True).at((x_col, y_vcc)))
    d.add(elm.Line().at((x_col, y_vcc)).right().length(1.18))
    d.add(
        elm.Label()
        .at((x_col - 0.08, y_vcc + 0.24))
        .label(f"+{vcc_val}" if vcc_val else "+VCC", halign="left")
    )
    rc = d.add(elm.Resistor().at((x_col, y_vcc - 0.03)).down().to((x_col, y_col)))
    rc_label = rf"$R_c$={rc_val}" if rc_val else r"$R_c$"
    d.add(elm.Label().at((x_col + 0.36, rc.center.y)).label(rc_label, halign="left"))
    col_node = d.add(elm.Dot().at((x_col, y_col)))

    # Collector node to transistor collector, aligned with short orthogonal routing.
    d.add(elm.Line().at(col_node.center).to((x_col, q.collector.y)))
    d.add(elm.Line().at((x_col, q.collector.y)).to((q.collector.x, q.collector.y)))

    # Left bias divider (Rb1, Rb2) from collector node to input node.
    d.add(elm.Line().at((x_col, y_col)).to((x_bias, y_col)))
    rb1 = d.add(elm.Resistor().at((x_bias, y_col)).down().to((x_bias, y_bias)))
    rb1_label = rf"$R_{{b1}}$={rb1_val}" if rb1_val else r"$R_{b1}$"
    d.add(elm.Label().at((x_bias - 0.24, rb1.center.y)).label(rb1_label, halign="right"))
    bias_node = d.add(elm.Dot().at((x_bias, y_bias)))

    rb2 = d.add(elm.Resistor().at((x_bias, y_bias)).down().to((x_bias, y_in)))
    rb2_label = rf"$R_{{b2}}$={rb2_val}" if rb2_val else r"$R_{b2}$"
    d.add(elm.Label().at((x_bias - 0.24, rb2.center.y)).label(rb2_label, halign="right"))
    in_node = d.add(elm.Dot().at((x_bias, y_in)))

    # Input source and local ground at divider bottom node.
    src = d.add(elm.SourceSin().at((0.62, y_in)).right())
    d.add(elm.Line().at(src.end).to(in_node.center))
    d.add(elm.Label().at((0.16, y_in + 0.02)).label(r"$V_{in}$", halign="right"))
    d.add(elm.Line().at(in_node.center).down().length(0.45))
    d.add(elm.Ground())

    # Direct bias path to base (capacitor removed per request).
    d.add(elm.Line().at((x_bias, y_bias)).right().to((4.25, y_bias)))
    d.add(elm.Line().at((4.25, y_bias)).right().to((q.base.x, q.base.y)))

    # Emitter output branch and load.
    out_node = d.add(elm.Dot().at((7.45, q.emitter.y)))
    d.add(elm.Line().at((q.emitter.x, q.emitter.y)).to(out_node.center))
    d.add(elm.Line().at(out_node.center).right().length(0.66))
    d.add(elm.Dot(open=True))
    d.add(elm.Label().at((8.1, q.emitter.y + 0.3)).label(r"$V_{out}$", halign="left"))

    re = d.add(elm.Resistor().at((q.emitter.x, q.emitter.y)).down().to((q.emitter.x, y_gnd)))
    re_label = rf"$R_e$={re_val}" if re_val else r"$R_e$"
    d.add(elm.Label().at((q.emitter.x - 0.35, re.center.y)).label(re_label, halign="right"))

    rl = d.add(elm.Resistor().at((out_node.center.x, out_node.center.y)).down().to((out_node.center.x, y_gnd)))
    rl_label = rf"$R_L$={rl_val}" if rl_val else r"$R_L$"
    d.add(elm.Label().at((out_node.center.x + 0.4, rl.center.y)).label(rl_label, halign="left"))

    # Shared ground bus and final ground symbol.
    d.add(elm.Line().at((q.emitter.x, y_gnd)).to((out_node.center.x, y_gnd)))
    d.add(elm.Dot().at((q.emitter.x, y_gnd)))
    d.add(elm.Dot().at((out_node.center.x, y_gnd)))
    d.add(elm.Line().at((out_node.center.x, y_gnd)).right().length(0.66))
    d.add(elm.Label().at((7.2, y_gnd - 0.42)).label("GND", fontsize=10))
    d.add(elm.Line().at((q.emitter.x, y_gnd)).down().length(0.56))
    d.add(elm.Ground())

    # Keep this topology clean and uncluttered.

    # Pin labels around transistor as in reference.
    d.add(elm.Label().at((q.collector.x + 0.15, q.collector.y + 0.05)).label("C", fontsize=10, halign="left"))
    d.add(elm.Label().at((q.base.x - 0.15, q.base.y - 0.1)).label("B", fontsize=10, halign="right"))
    d.add(elm.Label().at((q.emitter.x + 0.15, q.emitter.y - 0.02)).label("E", fontsize=10, halign="left"))

    return d



def draw_decoder(inputs: dict, outputs: dict, title: str = "2 x 4 Decoder") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Relative grid coordinates for stable, centered layout.
    origin_x = 3.1
    origin_y = 1.4
    box_w = 2.4
    box_h = 3.6
    left_x = origin_x
    right_x = origin_x + box_w
    bottom_y = origin_y
    top_y = origin_y + box_h
    center_x = left_x + box_w / 2
    center_y = bottom_y + box_h / 2
    d.move(dx=0.9, dy=0.3)

    # Heading aligned with approved style.
    _add_title(d, "2 x 4 Decoder Circuit", x=center_x, y=5.55)
    d.add(elm.Label().at((center_x, 5.25)).label("Digital Logic Configuration", fontsize=10, color="#444444"))

    # Decoder block.
    d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
    d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
    d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
    d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
    d.add(elm.Label().at((center_x, center_y + 0.2)).label("2 x 4", fontsize=11))
    d.add(elm.Label().at((center_x, center_y - 0.18)).label("Decoder", fontsize=12))

    # Left inputs A and B.
    in_len = 1.3
    y_a = center_y + 0.45
    y_b = center_y - 0.15
    for name, y in (("A", y_a), ("B", y_b)):
        d.add(elm.Line().at((left_x - in_len, y)).to((left_x, y)))
        d.add(elm.Arrow().at((left_x - 0.75, y)).right().length(0.34))
        val = _pick_value(inputs, name, name.lower())
        label = f"{name}={val}" if val else name
        d.add(elm.Label().at((left_x - in_len - 0.14, y)).label(label, halign="right", valign="center"))

    # Right outputs D0..D3.
    out_gap = 0.62
    out_len = 1.2
    y_top_out = center_y + 0.95
    for idx in range(4):
        y = y_top_out - idx * out_gap
        d.add(elm.Line().at((right_x, y)).to((right_x + out_len, y)))
        d.add(elm.Arrow().at((right_x + out_len - 0.48, y)).right().length(0.32))
        out_val = _pick_value(outputs, f"D{idx}", f"d{idx}", f"Y{idx}", f"y{idx}")
        label = f"D{idx}={out_val}" if out_val else rf"$D_{idx}$"
        d.add(elm.Label().at((right_x + out_len + 0.14, y)).label(label, halign="left", valign="center"))

    return d


def draw_encoder(inputs: dict, outputs: dict, title: str = "4 x 2 Encoder") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Relative grid coordinates for stable, centered layout.
    origin_x = 3.2
    origin_y = 1.5
    box_w = 2.4
    box_h = 2.8
    left_x = origin_x
    right_x = origin_x + box_w
    bottom_y = origin_y
    top_y = origin_y + box_h
    center_x = left_x + box_w / 2
    center_y = bottom_y + box_h / 2
    d.move(dx=0.85, dy=0.4)

    # Heading aligned with approved style.
    _add_title(d, "4 x 2 Encoder Circuit", x=center_x, y=5.55)
    d.add(elm.Label().at((center_x, 5.25)).label("Digital Logic Configuration", fontsize=10, color="#444444"))

    # Encoder block.
    d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
    d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
    d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
    d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
    d.add(elm.Label().at((center_x, center_y + 0.2)).label("4 x 2", fontsize=11))
    d.add(elm.Label().at((center_x, center_y - 0.18)).label("Encoder", fontsize=12))

    # Left inputs D0, D1, D2, D3 with vertical spacing.
    in_len = 1.3
    in_gap = 0.65
    y_top_in = center_y + 0.9
    for idx in range(4):
        y = y_top_in - idx * in_gap
        d.add(elm.Line().at((left_x - in_len, y)).to((left_x, y)))
        d.add(elm.Arrow().at((left_x - 0.75, y)).right().length(0.34))
        val = _pick_value(inputs, f"D{idx}", f"d{idx}")
        label = f"D{idx}={val}" if val else rf"$D_{idx}$"
        d.add(elm.Label().at((left_x - in_len - 0.14, y)).label(label, halign="right", valign="center"))

    # Right outputs Q0 and Q1.
    out_gap = 0.92
    out_len = 1.2
    y_top_out = center_y + 0.45
    for idx in range(2):
        y = y_top_out - idx * out_gap
        d.add(elm.Line().at((right_x, y)).to((right_x + out_len, y)))
        d.add(elm.Arrow().at((right_x + out_len - 0.48, y)).right().length(0.32))
        out_val = _pick_value(outputs, f"Q{idx}", f"q{idx}")
        label = f"Q{idx}={out_val}" if out_val else rf"$Q_{idx}$"
        d.add(elm.Label().at((right_x + out_len + 0.14, y)).label(label, halign="left", valign="center"))

    return d


def draw_priority_encoder(inputs: dict, outputs: dict, title: str = "Priority Encoder") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Stable centered geometry matching the provided reference style.
    origin_x = 3.25
    origin_y = 1.5
    box_w = 2.4
    box_h = 2.95
    left_x = origin_x
    right_x = origin_x + box_w
    bottom_y = origin_y
    top_y = origin_y + box_h
    center_x = left_x + box_w / 2
    center_y = bottom_y + box_h / 2
    d.move(dx=0.85, dy=0.4)

    # Heading aligned with prior approved digital diagrams.
    _add_title(d, "Priority Encoder Circuit", x=center_x, y=5.55)
    d.add(elm.Label().at((center_x, 5.25)).label("Digital Logic Configuration", fontsize=10, color="#444444"))

    # Encoder block.
    d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
    d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
    d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
    d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
    d.add(elm.Label().at((center_x, center_y + 0.18)).label("Priority", fontsize=12))
    d.add(elm.Label().at((center_x, center_y - 0.2)).label("Encoder", fontsize=12))

    # Left inputs in priority order from top (D3) to bottom (D0).
    in_len = 1.35
    in_gap = 0.67
    y_top_in = center_y + 0.96
    for idx in range(4):
        bit = 3 - idx
        y = y_top_in - idx * in_gap
        d.add(elm.Line().at((left_x - in_len, y)).to((left_x, y)))
        d.add(elm.Arrow().at((left_x - 0.75, y)).right().length(0.34))

        val = _pick_value(inputs, f"D{bit}", f"d{bit}", f"I{bit}", f"i{bit}")
        label = f"D{bit}={val}" if val else rf"$D_{bit}$"
        d.add(elm.Label().at((left_x - in_len - 0.14, y)).label(label, halign="right", valign="center"))

    # Priority annotations on the left, matching the reference semantics.
    note_x = left_x - in_len - 0.95
    y_high = y_top_in + 0.55
    y_low = y_top_in - 3 * in_gap - 0.55
    d.add(elm.Label().at((note_x, y_high)).label("Highest priority\ninput", halign="center", valign="bottom", fontsize=10))
    d.add(elm.Arrow().at((left_x - in_len - 0.35, y_high - 0.03)).down().length(0.36))

    d.add(elm.Label().at((note_x, y_low)).label("Lowest priority\ninput", halign="center", valign="top", fontsize=10))
    d.add(elm.Arrow().at((left_x - in_len - 0.35, y_low + 0.03)).up().length(0.36))

    # If model outputs are missing, derive Y1/Y0 from input priority so labels
    # still show useful values like Y0=0 rather than only symbol names.
    def _as_logic_bit(value: str) -> int | None:
        if value == "":
            return None
        try:
            numeric = float(value)
        except ValueError:
            return None
        if numeric == 0:
            return 0
        if numeric == 1:
            return 1
        return None

    d3 = _as_logic_bit(_pick_value(inputs, "D3", "d3", "I3", "i3"))
    d2 = _as_logic_bit(_pick_value(inputs, "D2", "d2", "I2", "i2"))
    d1 = _as_logic_bit(_pick_value(inputs, "D1", "d1", "I1", "i1"))
    d0 = _as_logic_bit(_pick_value(inputs, "D0", "d0", "I0", "i0"))

    derived_y1 = None
    derived_y0 = None
    if None not in (d3, d2, d1, d0):
        if d3 == 1:
            derived_y1, derived_y0 = 1, 1
        elif d2 == 1:
            derived_y1, derived_y0 = 1, 0
        elif d1 == 1:
            derived_y1, derived_y0 = 0, 1
        else:
            derived_y1, derived_y0 = 0, 0

    # Right outputs Y1, Y0.
    out_len = 1.25
    out_gap = 1.18
    y_top_out = center_y + 0.58
    for bit in (1, 0):
        y = y_top_out - (1 - bit) * out_gap
        d.add(elm.Line().at((right_x, y)).to((right_x + out_len, y)))
        d.add(elm.Arrow().at((right_x + out_len - 0.5, y)).right().length(0.33))

        out_val = _pick_value(outputs, f"Y{bit}", f"y{bit}", f"Q{bit}", f"q{bit}")
        if not out_val:
            if bit == 1 and derived_y1 is not None:
                out_val = str(derived_y1)
            if bit == 0 and derived_y0 is not None:
                out_val = str(derived_y0)

        label = f"Y{bit}={out_val}" if out_val else rf"$Y_{bit}$"
        d.add(elm.Label().at((right_x + out_len + 0.14, y)).label(label, halign="left", valign="center"))

    return d


def draw_demux(inputs: dict, outputs: dict, title: str = "1:4 DEMUX") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Relative grid layout for clean and stable geometry.
    # Box is intentionally dominant; wires and arrows are slim/minimal.
    origin_x = 3.2
    origin_y = 1.6
    box_w = 2.2
    box_h = 3.6
    left_x = origin_x
    right_x = origin_x + box_w
    bottom_y = origin_y
    top_y = origin_y + box_h
    center_x = left_x + box_w / 2
    center_y = bottom_y + box_h / 2

    # Center the composition in the canvas.
    d.move(dx=1.0, dy=0.4)

    # Draw block edges explicitly so wire endpoints can share exact coordinates.
    d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
    d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
    d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
    d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
    d.add(elm.Label().at((center_x, center_y + 0.28)).label("1:4", fontsize=11))
    d.add(elm.Label().at((center_x, center_y - 0.12)).label("DEMUX", fontsize=12))

    # Input I centered on block.
    wire_pad = 1.5
    input_start_x = left_x - wire_pad
    y_in = center_y
    d.add(elm.Line().at((input_start_x, y_in)).to((left_x, y_in)))
    d.add(elm.Arrow().at((left_x - 0.8, y_in)).right().length(0.42))
    in_val = _pick_value(inputs, "I", "i")
    in_label = f"I={in_val}" if in_val else "I"
    d.add(elm.Label().at((input_start_x - 0.15, y_in)).label(in_label, halign="right", valign="center"))

    # Outputs Y0..Y3 with equal vertical spacing.
    output_gap = 0.72
    y_top_out = center_y + 1.08
    out_len = 1.35
    for idx in range(4):
        y = y_top_out - idx * output_gap
        d.add(elm.Line().at((right_x, y)).to((right_x + out_len, y)))
        d.add(elm.Arrow().at((right_x + out_len - 0.55, y)).right().length(0.34))
        out_val = _pick_value(outputs, f"Y{idx}", f"y{idx}")
        out_label = f"Y{idx}={out_val}" if out_val else rf"$Y_{idx}$"
        d.add(elm.Label().at((right_x + out_len + 0.18, y)).label(out_label, halign="left", valign="center"))

    # Select lines centered and symmetric under block.
    sel_offset = 0.45
    x_s1 = center_x - sel_offset
    x_s0 = center_x + sel_offset
    sel_bottom_y = bottom_y - 1.15
    s1_val = _pick_value(inputs, "S1", "s1")
    s0_val = _pick_value(inputs, "S0", "s0")
    for x_sel, label, sel_val in ((x_s1, r"$S_1$", s1_val), (x_s0, r"$S_0$", s0_val)):
        d.add(elm.Line().at((x_sel, sel_bottom_y)).to((x_sel, bottom_y)))
        d.add(elm.Arrow().at((x_sel, sel_bottom_y + 0.4)).up().length(0.34))
        sel_label = f"{label}={sel_val}" if sel_val else label
        d.add(elm.Label().at((x_sel, sel_bottom_y - 0.12)).label(sel_label, halign="center", valign="top"))

    return d


def draw_full_adder(inputs: dict, outputs: dict, title: str = "Full Adder") -> schemdraw.Drawing:
    """Draw a clean full adder block diagram matching reference topology.
    
    Three inputs (A, B, C_in) on left â†’ central block â†’ two outputs (S, C_out) on right.
    No side panels; values shown next to labels.
    """
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Centered block geometry.
    origin_x = 3.4
    origin_y = 1.6
    box_w = 2.0
    box_h = 2.2
    left_x = origin_x
    right_x = origin_x + box_w
    bottom_y = origin_y
    top_y = origin_y + box_h
    center_x = left_x + box_w / 2
    center_y = bottom_y + box_h / 2
    
    # Center the composition in the canvas.
    d.move(dx=0.95, dy=0.5)

    # Draw block edges.
    d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
    d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
    d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
    d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
    d.add(elm.Label().at((center_x, center_y)).label("Full\nAdder", fontsize=12, halign="center", valign="center"))

    # Left inputs: A, B, C_in with vertical spacing from top to bottom.
    in_len = 1.2
    in_gap = 0.73
    y_top_in = center_y + 0.65
    
    input_specs = [
        ("A", "a"),
        ("B", "b"),
        (r"$C_{in}$", "cin", "c_in"),
    ]
    
    for idx, input_spec in enumerate(input_specs):
        y = y_top_in - idx * in_gap
        # Draw input line and arrow.
        d.add(elm.Line().at((left_x - in_len, y)).to((left_x, y)))
        d.add(elm.Arrow().at((left_x - 0.7, y)).right().length(0.32))
        
        # Get value from inputs dict.
        label_key = input_spec[0]
        val_keys = input_spec[1:] if len(input_spec) > 1 else (input_spec[0].lower(),)
        val = _pick_value(inputs, *val_keys)
        
        # Format label with value or just the label.
        if val:
            if label_key.startswith("$"):
                label = f"{label_key[:-1]}={val}$"
            else:
                label = f"{label_key}={val}"
        else:
            label = label_key
        
        d.add(elm.Label().at((left_x - in_len - 0.12, y)).label(label, halign="right", valign="center"))

    # Right outputs: S (Sum), C_out (Carry Out).
    out_gap = 1.1
    out_len = 1.2
    y_top_out = center_y + 0.35
    
    def _as_bit(raw: str) -> int | None:
        if raw == "":
            return None
        try:
            value = int(round(float(raw)))
        except ValueError:
            return None
        return value if value in (0, 1) else None

    a_bit = _as_bit(_pick_value(inputs, "A", "a"))
    b_bit = _as_bit(_pick_value(inputs, "B", "b"))
    cin_bit = _as_bit(_pick_value(inputs, "Cin", "cin", "c_in"))
    derived_sum = None
    derived_carry = None
    if None not in (a_bit, b_bit, cin_bit):
        derived_sum = (a_bit ^ b_bit) ^ cin_bit
        derived_carry = (a_bit & b_bit) | (a_bit & cin_bit) | (b_bit & cin_bit)

    output_specs = [
        ("S", "sum", "s", "y0", "y_0", "sum_out"),
        (r"$C_{out}$", "carry", "c_out", "cout", "carry_out", "y1", "y_1"),
    ]
    
    for idx, output_spec in enumerate(output_specs):
        y = y_top_out - idx * out_gap
        # Draw output line and arrow.
        d.add(elm.Line().at((right_x, y)).to((right_x + out_len, y)))
        d.add(elm.Arrow().at((right_x + out_len - 0.44, y)).right().length(0.32))
        
        # Get value from outputs dict.
        label_key = output_spec[0]
        val_keys = output_spec[1:]
        out_val = _pick_value(outputs, *val_keys)
        if not out_val:
            if label_key == "S" and derived_sum is not None:
                out_val = str(derived_sum)
            if label_key == r"$C_{out}$" and derived_carry is not None:
                out_val = str(derived_carry)
        
        # Format label with value or just the label.
        if out_val:
            if label_key.startswith("$"):
                label = f"{label_key[:-1]}={out_val}$"
            else:
                label = f"{label_key}={out_val}"
        else:
            label = label_key
        
        d.add(elm.Label().at((right_x + out_len + 0.12, y)).label(label, halign="left", valign="center"))

    # Professional heading at top (no side panel).
    _add_title(d, "Full Adder Circuit", x=center_x, y=5.4)
    d.add(elm.Label().at((center_x, 5.05)).label("Block Diagram", fontsize=10, color="#444444"))

    return d


def draw_mux(inputs: dict, outputs: dict, title: str = "4:1 Multiplexer") -> schemdraw.Drawing:
    """Draw a clean 4:1 multiplexer block diagram matching reference topology.
    
    Four data inputs (I0, I1, I2, I3) on left â†’ central block â†’ one output (Y) on right.
    Two select lines (S1, S0) at bottom.
    No side panels; values shown next to labels.
    """
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Centered block geometry.
    origin_x = 3.2
    origin_y = 1.4
    box_w = 2.2
    box_h = 2.8
    left_x = origin_x
    right_x = origin_x + box_w
    bottom_y = origin_y
    top_y = origin_y + box_h
    center_x = left_x + box_w / 2
    center_y = bottom_y + box_h / 2
    
    # Center the composition in the canvas.
    d.move(dx=0.9, dy=0.4)

    # Draw block edges.
    d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
    d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
    d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
    d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
    d.add(elm.Label().at((center_x, center_y + 0.15)).label("4 : 1", fontsize=11, halign="center", valign="center"))
    d.add(elm.Label().at((center_x, center_y - 0.25)).label("Multiplexer", fontsize=12, halign="center", valign="center"))

    # Left data inputs: I0, I1, I2, I3 with vertical spacing from top to bottom.
    in_len = 1.25
    in_gap = 0.7
    y_top_in = center_y + 0.85
    
    for idx in range(4):
        y = y_top_in - idx * in_gap
        # Draw input line and arrow.
        d.add(elm.Line().at((left_x - in_len, y)).to((left_x, y)))
        d.add(elm.Arrow().at((left_x - 0.7, y)).right().length(0.32))
        
        # Get value from inputs dict.
        val = _pick_value(inputs, f"I{idx}", f"i{idx}")
        label = f"I{idx}={val}" if val else rf"$I_{idx}$"
        
        d.add(elm.Label().at((left_x - in_len - 0.12, y)).label(label, halign="right", valign="center"))


    # Right output: Y with "Output" label stacked above.
    out_len = 1.2
    y_out = center_y
    d.add(elm.Line().at((right_x, y_out)).to((right_x + out_len, y_out)))
    d.add(elm.Arrow().at((right_x + out_len - 0.44, y_out)).right().length(0.32))

    out_val = _pick_value(outputs, "Y", "y")
    base_x = right_x + out_len + 0.16
    base_y = y_out
    out_label = f"Y={out_val}" if out_val else "Y"
    d.add(elm.Label().at((base_x, base_y)).label(out_label, halign="left", valign="center"))

    # Bottom select lines: S1 (left), S0 (right)
    sel_offset = 0.55
    x_s1 = center_x - sel_offset
    x_s0 = center_x + sel_offset
    sel_bottom_y = bottom_y - 1.1
    
    for x_sel, label_str, val_keys in [(x_s1, r"$S_1$", ("S1", "s1")), (x_s0, r"$S_0$", ("S0", "s0"))]:
        d.add(elm.Line().at((x_sel, sel_bottom_y)).to((x_sel, bottom_y)))
        d.add(elm.Arrow().at((x_sel, sel_bottom_y + 0.4)).up().length(0.34))
        sel_val = _pick_value(inputs, *val_keys)
        sel_label = f"{label_str}={sel_val}" if sel_val else label_str
        d.add(elm.Label().at((x_sel, sel_bottom_y - 0.12)).label(sel_label, halign="center", valign="top"))

    # Professional heading at top (no side panel).
    _add_title(d, "4:1 Multiplexer Circuit", x=center_x, y=5.4)
    d.add(elm.Label().at((center_x, 5.05)).label("Digital Logic Block", fontsize=10, color="#444444"))

    return d





def draw_up_counter(inputs: dict, outputs: dict, title: str = "Up Counter") -> schemdraw.Drawing:
    """Draw a 3-bit synchronous up-counter using T flip-flops (reference style)."""
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)
    d.move(dx=0.55, dy=0.3)

    # Top heading: centered, slightly higher, professional tone.
    _add_title(d, "3-bit Synchronous Up Counter", x=5.25, y=6.05)
    d.add(elm.Label().at((5.25, 5.74)).label("T Flip-Flop Logic Implementation", fontsize=10, color="#444444"))

    mode_val = _pick_value(inputs, "Mode", "mode") or _pick_value(outputs, "Mode", "mode")
    if mode_val:
        mode_text = "UP" if mode_val in {"1", "1.0"} else mode_val
        d.add(elm.Label().at((5.25, 5.48)).label(rf"$Mode$={mode_text}", fontsize=10, color="#555555"))

    # Core geometry for three cascaded T flip-flops.
    base_x = 1.45
    base_y = 1.85
    ff_w = 1.55
    ff_h = 2.05
    ff_gap = 1.2
    ff23_extra_gap = 0.62

    stage_left_x = [
        base_x,
        base_x + ff_w + ff_gap,
        base_x + 2 * (ff_w + ff_gap) + ff23_extra_gap,
    ]

    t_pins = []
    clk_pins = []
    q_pins = []

    for idx in range(3):
        left_x = stage_left_x[idx]
        right_x = left_x + ff_w
        bottom_y = base_y
        top_y = bottom_y + ff_h
        center_x = left_x + ff_w / 2
        center_y = bottom_y + ff_h / 2

        t_pin = (left_x, top_y - 0.58)
        clk_pin = (left_x, bottom_y + 0.56)
        q_pin = (right_x, top_y - 0.58)

        t_pins.append(t_pin)
        clk_pins.append(clk_pin)
        q_pins.append(q_pin)

        # Flip-flop body.
        d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
        d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
        d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
        d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))

        d.add(elm.Label().at((left_x + 0.22, t_pin[1])).label(rf"$T_{idx}$", halign="left", valign="center", fontsize=10))
        d.add(elm.Label().at((right_x - 0.16, q_pin[1])).label(rf"$Q_{idx}$", halign="right", valign="center", fontsize=10))
        d.add(elm.Label().at((center_x, center_y - 0.02)).label("T", fontsize=12))
        d.add(elm.Label().at((center_x, center_y - 0.42)).label("Flip-Flop", fontsize=10))

        # Clock marker at each flip-flop input.
        tri_dx = 0.18
        tri_dy = 0.13
        d.add(elm.Line().at((left_x, clk_pin[1])).to((left_x + tri_dx, clk_pin[1] + tri_dy)))
        d.add(elm.Line().at((left_x + tri_dx, clk_pin[1] + tri_dy)).to((left_x + tri_dx, clk_pin[1] - tri_dy)))
        d.add(elm.Line().at((left_x + tri_dx, clk_pin[1] - tri_dy)).to((left_x, clk_pin[1])))

    # T0 is tied to logic 1.
    left_const_x = t_pins[0][0] - 1.05
    d.add(elm.Line().at((left_const_x, t_pins[0][1])).to(t_pins[0]))
    d.add(elm.Arrow().at((left_const_x + 0.48, t_pins[0][1])).right().length(0.3))
    d.add(elm.Label().at((left_const_x - 0.14, t_pins[0][1])).label("1", halign="right", valign="center"))

    # T1 is driven by Q0.
    d.add(elm.Line().at(q_pins[0]).to((t_pins[1][0], q_pins[0][1])))
    d.add(elm.Arrow().at((t_pins[1][0] - 0.5, q_pins[0][1])).right().length(0.28))

    # AND block for T2 = Q1 AND Q0.
    and_left = q_pins[1][0] + 0.34
    and_w = 0.72
    and_h = 0.9
    and_bottom = t_pins[2][1] - and_h / 2
    and_top = and_bottom + and_h
    and_mid = and_bottom + and_h / 2
    and_in_top = (and_left, and_bottom + 0.66)
    and_in_bot = (and_left, and_bottom + 0.24)
    and_out = (and_left + and_w, and_mid)

    d.add(elm.Line().at((and_left, and_bottom)).to((and_left, and_top)))
    d.add(elm.Line().at((and_left, and_top)).to((and_left + and_w, and_top)))
    d.add(elm.Line().at((and_left + and_w, and_top)).to((and_left + and_w, and_bottom)))
    d.add(elm.Line().at((and_left + and_w, and_bottom)).to((and_left, and_bottom)))
    d.add(elm.Label().at((and_left + and_w / 2, and_mid)).label("AND", fontsize=8))

    # Q1 to upper AND input.
    d.add(elm.Line().at(q_pins[1]).to((and_in_top[0], q_pins[1][1])))
    d.add(elm.Line().at((and_in_top[0], q_pins[1][1])).to(and_in_top))

    # Q0 branch to lower AND input (routed above text to avoid overlap).
    q0_branch_top_y = q_pins[0][1] + 0.5
    q0_join_x = and_left - 0.24
    d.add(elm.Line().at(q_pins[0]).to((q0_join_x, q_pins[0][1])))
    d.add(elm.Line().at((q0_join_x, q_pins[0][1])).to((q0_join_x, q0_branch_top_y)))
    d.add(elm.Line().at((q0_join_x, q0_branch_top_y)).to((and_in_bot[0], q0_branch_top_y)))
    d.add(elm.Line().at((and_in_bot[0], q0_branch_top_y)).to(and_in_bot))

    # AND output drives T2.
    d.add(elm.Line().at(and_out).to((t_pins[2][0], and_out[1])))
    d.add(elm.Arrow().at((t_pins[2][0] - 0.5, and_out[1])).right().length(0.28))

    # Shared clock bus routed below all stages.
    clk_bus_y = base_y - 1.05
    clk_left = t_pins[0][0] - 1.25
    clk_right = q_pins[2][0] + 1.95
    d.add(elm.Line().at((clk_left, clk_bus_y)).to((clk_right, clk_bus_y)))
    d.add(elm.Arrow().at((clk_left + 0.54, clk_bus_y)).right().length(0.34))
    d.add(elm.Label().at((clk_left - 0.08, clk_bus_y - 0.14)).label("clk", halign="right", valign="top"))

    for clk_pin in clk_pins:
        tap_x = clk_pin[0] - 0.36
        d.add(elm.Line().at((tap_x, clk_bus_y)).to((tap_x, clk_pin[1])))
        d.add(elm.Line().at((tap_x, clk_pin[1])).to(clk_pin))

    # Counter output from Q2 (right-most stage), matching reference routing style.
    q2_out_x = q_pins[2][0] + 0.62
    out_y = clk_bus_y + 0.52
    d.add(elm.Line().at(q_pins[2]).to((q2_out_x, q_pins[2][1])))
    d.add(elm.Line().at((q2_out_x, q_pins[2][1])).to((q2_out_x, out_y)))
    d.add(elm.Line().at((q2_out_x, out_y)).to((clk_right, out_y)))
    d.add(elm.Arrow().at((clk_right - 0.56, out_y)).right().length(0.34))
    d.add(elm.Label().at((clk_right + 0.1, out_y)).label("Counter\nOutput", halign="left", valign="center"))

    # Show state values directly at the Q labels (local, no side panel).
    for idx in range(3):
        bit_val = _pick_value(outputs, f"Next_Q{idx}", f"next_q{idx}")
        if not bit_val:
            bit_val = _pick_value(inputs, f"Q{idx}", f"q{idx}")
        if bit_val:
            d.add(elm.Label().at((q_pins[idx][0] + 0.1, q_pins[idx][1] + 0.24)).label(rf"$Q_{idx}$={bit_val}", halign="left", fontsize=9))

    return d





def draw_down_counter(inputs: dict, outputs: dict, title: str = "Down Counter") -> schemdraw.Drawing:
    d = _new_drawing()
    d.config(lw=1.35, fontsize=11)

    # Centered, reference-matched geometry for JK ripple counter.
    base_x = 2.1
    base_y = 1.75
    ff_w = 1.55
    ff_h = 2.05
    ff_gap = 1.25
    d.move(dx=0.55, dy=0.25)

    # Heading: top-centered and professional.
    _add_title(d, "3-bit Asynchronous Down Counter", x=5.25, y=5.92)
    d.add(elm.Label().at((5.25, 5.62)).label("JK Flip-Flop Ripple Architecture", fontsize=10, color="#444444"))

    cp_val = _pick_value(inputs, "CP", "CLK", "clk")
    high_val = _pick_value(inputs, "HIGH", "VCC", "vcc")

    # Pin coordinate arrays.
    j_pins = []
    k_pins = []
    clk_pins = []
    q_pins = []
    qbar_pins = []

    for idx in range(3):
        stage_no = idx + 1
        left_x = base_x + idx * (ff_w + ff_gap)
        right_x = left_x + ff_w
        bottom_y = base_y
        top_y = bottom_y + ff_h
        center_x = left_x + ff_w / 2
        center_y = bottom_y + ff_h / 2

        j_pin = (left_x, top_y - 0.58)
        clk_pin = (left_x, center_y)
        k_pin = (left_x, bottom_y + 0.58)
        q_pin = (right_x, top_y - 0.58)
        qbar_pin = (right_x, bottom_y + 0.58)

        j_pins.append(j_pin)
        k_pins.append(k_pin)
        clk_pins.append(clk_pin)
        q_pins.append(q_pin)
        qbar_pins.append(qbar_pin)

        # JK FF block with explicit pin labels.
        d.add(elm.Line().at((left_x, bottom_y)).to((left_x, top_y)))
        d.add(elm.Line().at((left_x, top_y)).to((right_x, top_y)))
        d.add(elm.Line().at((right_x, top_y)).to((right_x, bottom_y)))
        d.add(elm.Line().at((right_x, bottom_y)).to((left_x, bottom_y)))
        d.add(elm.Label().at((center_x, center_y + 0.22)).label("JK FF", fontsize=11))
        d.add(elm.Label().at((center_x, center_y - 0.12)).label(str(stage_no), fontsize=10))

        d.add(elm.Label().at((left_x + 0.15, j_pin[1])).label("J", halign="left", valign="center", fontsize=9))
        d.add(elm.Label().at((left_x + 0.15, k_pin[1])).label("K", halign="left", valign="center", fontsize=9))
        d.add(elm.Label().at((right_x - 0.14, q_pin[1])).label("Q", halign="right", valign="center", fontsize=9))
        d.add(elm.Label().at((right_x - 0.14, qbar_pin[1])).label(r"$\overline{Q}$", halign="right", valign="center", fontsize=9))

        # Clock marker at left edge.
        tri_dx = 0.18
        tri_dy = 0.13
        d.add(elm.Line().at((left_x, clk_pin[1])).to((left_x + tri_dx, clk_pin[1] + tri_dy)))
        d.add(elm.Line().at((left_x + tri_dx, clk_pin[1] + tri_dy)).to((left_x + tri_dx, clk_pin[1] - tri_dy)))
        d.add(elm.Line().at((left_x + tri_dx, clk_pin[1] - tri_dy)).to((left_x, clk_pin[1])))

    # HIGH rail feeding J and K pins on all stages.
    high_y = base_y + ff_h + 0.74
    high_left_x = base_x - 1.25
    high_right_x = base_x + 3 * ff_w + 2 * ff_gap + 0.7
    d.add(elm.Line().at((high_left_x, high_y)).to((high_right_x, high_y)))
    d.add(elm.Arrow().at((high_left_x + 0.66, high_y)).right().length(0.32))
    high_label = rf"HIGH={high_val}" if high_val else "HIGH"
    d.add(elm.Label().at((high_left_x - 0.15, high_y)).label(high_label, halign="right", valign="center"))

    for idx in range(3):
        junction_x = j_pins[idx][0]
        mid_y = (j_pins[idx][1] + k_pins[idx][1]) / 2
        d.add(elm.Line().at((junction_x, high_y)).to((junction_x, mid_y)))
        d.add(elm.Line().at((junction_x, mid_y)).to(j_pins[idx]))
        d.add(elm.Line().at((junction_x, mid_y)).to(k_pins[idx]))

    # CP input to first clock pin.
    cp_left_x = clk_pins[0][0] - 1.25
    d.add(elm.Line().at((cp_left_x, clk_pins[0][1])).to(clk_pins[0]))
    d.add(elm.Arrow().at((cp_left_x + 0.6, clk_pins[0][1])).right().length(0.32))
    cp_label = rf"$CP$={cp_val}" if cp_val else "$CP$"
    d.add(elm.Label().at((cp_left_x - 0.12, clk_pins[0][1])).label(cp_label, halign="right", valign="center"))

    # Ripple clock chain: Q_n drives next stage clock.
    for idx in range(2):
        x1, y1 = q_pins[idx]
        x2, y2 = clk_pins[idx + 1]
        d.add(elm.Line().at((x1, y1)).to((x1 + 0.48, y1)))
        d.add(elm.Line().at((x1 + 0.48, y1)).to((x1 + 0.48, y2)))
        d.add(elm.Line().at((x1 + 0.48, y2)).to((x2, y2)))
        d.add(elm.Arrow().at((x2 - 0.52, y2)).right().length(0.28))

    # Stage outputs from Q-bar pins with true subscript notation.
    out_tags = ["A", "B", "C"]
    in_keys = ["Q2", "Q1", "Q0"]
    out_keys = ["Next_Q2", "Next_Q1", "Next_Q0"]
    for idx in range(3):
        x_out, y_out = qbar_pins[idx]
        y_drop = y_out - 1.35
        d.add(elm.Line().at((x_out, y_out)).to((x_out, y_drop)))
        d.add(elm.Arrow().at((x_out, y_drop + 0.36)).down().length(0.28))

        present = _pick_value(inputs, in_keys[idx], in_keys[idx].lower())
        nxt = _pick_value(outputs, out_keys[idx], out_keys[idx].lower())
        if nxt:
            label = rf"$\overline{{Q_{out_tags[idx]}}}$={nxt}"
        elif present:
            label = rf"$\overline{{Q_{out_tags[idx]}}}$={present}"
        else:
            label = rf"$\overline{{Q_{out_tags[idx]}}}$"
        d.add(elm.Label().at((x_out, y_drop - 0.08)).label(label, halign="center", valign="top"))

    return d

