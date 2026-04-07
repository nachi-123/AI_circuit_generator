from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import requests

try:
	from sklearn.exceptions import InconsistentVersionWarning
except Exception:  # pragma: no cover - sklearn API differences across versions
	InconsistentVersionWarning = None


BASE_DIR = Path(__file__).resolve().parent
FORWARD_DIR = BASE_DIR / "models" / "models_forward"
BACKWARD_DIR = BASE_DIR / "models" / "models_backward"
DATASET_DIR = BASE_DIR / "datasets"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
MODEL_CACHE: dict[Path, Any] = {}
MODEL_EXTENSIONS = ("*.joblib", "*.pkl")
GLOBAL_DEFAULTS_CACHE: dict[str, float] | None = None

# Last-resort defaults when neither circuit-level nor global medians are available.
COMMON_PARAMETER_DEFAULTS: dict[str, float] = {
	"valid": 1.0,
	"supply_voltage_v": 5.0,
	"temperature_c": 25.0,
	"propagation_delay_ns": 10.0,
}

# Suppress noisy sklearn version and feature name warnings
warnings.filterwarnings("ignore", message=".*Inconsistent.*ersion.*")
warnings.filterwarnings("ignore", message=".*does not have valid feature names.*")
warnings.filterwarnings("ignore", message=".*Trying to unpickle estimator.*")
if InconsistentVersionWarning is not None:
	warnings.filterwarnings("ignore", category=InconsistentVersionWarning)


@dataclass
class ModelChoice:
	key: str
	direction: str
	path: Path


DIGITAL_KEYWORDS = {
	"logic",
	"boolean",
	"bit",
	"bits",
	"truth",
	"gate",
	"adder",
	"subtractor",
	"counter",
	"mux",
	"demux",
	"encoder",
	"decoder",
	"nand",
	"nor",
	"xor",
	"xnor",
	"not",
	"sum",
	"carry",
	"borrow",
	"cin",
	"bin",
}

ANALOG_KEYWORDS = {
	"analog",
	"amplifier",
	"voltage",
	"current",
	"frequency",
	"gain",
	"bandwidth",
	"cutoff",
	"filter",
	"lowpass",
	"low_pass",
	"highpass",
	"rc",
	"capacitor",
	"inductor",
	"resistor",
	"bias",
	"vcc",
	"vdd",
	"vin",
	"vout",
	"vce",
	"vds",
	"integrator",
	"differentiator",
	"inverting",
	"non_inverting",
	"rectifier",
	"clamper",
	"clipper",
}

DIGITAL_CIRCUIT_HINTS = {
	"and",
	"or",
	"not",
	"nand",
	"nor",
	"xor",
	"xnor",
	"half_adder",
	"full_adder",
	"half_subtractor",
	"full_subtractor",
	"comparator",
	"mux",
	"demux",
	"encoder",
	"decoder",
	"priority_encoder",
	"counter",
	"up_counter",
	"down_counter",
	"up_down_counter",
	"mod_n_counter",
}

# Circuit-specific parameter priority when legacy models lack feature names.
# We select the most important dataset columns first, then fill remaining slots
# in dataset order to satisfy model input size.
ANALOG_PARAM_PRIORITIES: dict[str, dict[str, list[str]]] = {
	"cb": {
		"forward": ["Rc", "Re", "Rb1", "Rb2", "RL", "Vcc"],
		"backward": ["Av", "fH", "Ic", "Vce"],
	},
	"ce": {
		"forward": ["Re", "Rb1", "Rb2", "RL", "Vcc", "Rc"],
		"backward": ["Av", "fH", "Ie", "Ic", "Vce"],
	},
	"cc": {
		"forward": ["Rc", "Re", "Rb1", "Rb2", "RL", "Vcc"],
		"backward": ["Av", "fH", "Ie", "Vce"],
	},
}


def normalize_key(text: str) -> str:
	text = text.strip().lower()
	text = re.sub(r"[^a-z0-9]+", "_", text)
	text = re.sub(r"_+", "_", text).strip("_")
	return text


def pretty_label(key: str) -> str:
	return key.replace("_", " ").title()


def model_key_from_stem(stem: str) -> str:
	key = stem.strip()
	if key.startswith("F_") or key.startswith("B_"):
		key = key[2:]
	key = re.sub(r"_model\s*$", "", key)
	return normalize_key(key)


def iter_model_files(folder: Path) -> list[Path]:
	files: list[Path] = []
	for pattern in MODEL_EXTENSIONS:
		files.extend(folder.glob(pattern))
	# Deduplicate in case extension patterns overlap and keep stable ordering.
	return sorted(set(files), key=lambda p: p.name.lower())


def dataset_key_from_stem(stem: str) -> str:
	return normalize_key(re.sub(r"_dataset$", "", stem))


def discover_models() -> dict[str, dict[str, Path]]:
	catalog: dict[str, dict[str, Path]] = {"forward": {}, "backward": {}}

	for direction, folder in (("forward", FORWARD_DIR), ("backward", BACKWARD_DIR)):
		if not folder.exists():
			continue

		grouped: dict[str, list[Path]] = {}
		for p in iter_model_files(folder):
			key = model_key_from_stem(p.stem)
			grouped.setdefault(key, []).append(p)

		for key, candidates in grouped.items():
			# Prefer *_model artifacts when duplicates exist.
			candidates_sorted = sorted(
				candidates,
				key=lambda p: (0 if p.stem.strip().endswith("_model") else 1, len(p.name), p.name),
			)
			catalog[direction][key] = candidates_sorted[0]

	return catalog


def discover_model_inventory() -> dict[str, list[Path]]:
	inventory: dict[str, list[Path]] = {"forward": [], "backward": []}
	for direction, folder in (("forward", FORWARD_DIR), ("backward", BACKWARD_DIR)):
		if not folder.exists():
			continue
		inventory[direction] = iter_model_files(folder)
	return inventory


def load_dataset_columns() -> dict[str, list[str]]:
	data: dict[str, list[str]] = {}
	if not DATASET_DIR.exists():
		return data

	for p in DATASET_DIR.rglob("*.csv"):
		try:
			cols = list(pd.read_csv(p, nrows=1).columns)
			key = dataset_key_from_stem(p.stem)
			# Keep first seen mapping to avoid accidental overrides by similarly named files.
			data.setdefault(key, cols)
		except Exception:
			continue
	return data


def dataset_cols_for_circuit(circuit_key: str, all_dataset_cols: dict[str, list[str]]) -> list[str] | None:
	"""Resolve dataset columns for a circuit key across varied CSV naming conventions."""
	ck = normalize_key(circuit_key)
	if not ck:
		return None

	if ck in all_dataset_cols:
		return all_dataset_cols[ck]

	best_key: str | None = None
	best_score = -1
	for dk in all_dataset_cols.keys():
		nk = normalize_key(dk)
		score = 0
		if nk == ck:
			score = 100
		elif nk.endswith("_" + ck):
			score = 80
		elif ck in nk.split("_"):
			score = 60
		elif ck in nk:
			score = 20

		if score > best_score:
			best_score = score
			best_key = dk

	if best_key is not None and best_score > 0:
		return all_dataset_cols[best_key]

	return None


def load_model(path: Path):
	if path not in MODEL_CACHE:
		MODEL_CACHE[path] = joblib.load(path)
	return MODEL_CACHE[path]


def alias_map(catalog: dict[str, dict[str, Path]], inventory: dict[str, list[Path]]) -> dict[str, str]:
	aliases: dict[str, str] = {}

	synonyms: dict[str, str] = {
		"rc_lowpass": "rc_lpf",
		"rc_low_pass": "rc_lpf",
		"rc_low_pass_filter": "rc_lpf",
		"rc_highpass": "rc_highpass",
		"rc_high_pass": "rc_highpass",
		"rl_lowpass": "rl_lowpass",
		"rl_low_pass": "rl_lowpass",
		"rl_highpass": "rl_highpass",
		"rl_high_pass": "rl_highpass",
		"rlc_parallel_bandpass": "rlc_parallel_bandpass",
		"tlc_parallel_bandpass": "rlc_parallel_bandpass",
		"rlc_series_bandpass": "rlc_series_bandpass",
		# User-friendly shorthand names.
		"log": "log_amplifier",
		"antilog": "antilog_amplifier",
		"halfwave": "half_wave_rectifier",
		"fullwave": "full_wave_rectifier",
	}

	for direction in ("forward", "backward"):
		for key in catalog[direction].keys():
			variants = {
				key,
				key.replace("_", " "),
				key.replace("_", ""),
			}
			for v in variants:
				aliases[normalize_key(v)] = key

		# Include aliases derived from every artifact stem so "extra" models
		# can still resolve to their canonical circuit key.
		for p in inventory[direction]:
			canonical = model_key_from_stem(p.stem)
			artifact_variants = {
				p.stem,
				p.stem.replace("_", " "),
				re.sub(r"^[FB]_", "", p.stem),
				re.sub(r"^[FB]_", "", p.stem).replace("_", " "),
				model_key_from_stem(p.stem),
			}
			for v in artifact_variants:
				aliases[normalize_key(v)] = canonical

	for alias, target in synonyms.items():
		aliases[normalize_key(alias)] = target
		aliases[normalize_key(alias.replace("_", " "))] = target

	return aliases


OLLAMA_CACHE: dict[str, dict[str, Any]] = {}

def call_ollama_for_intent(user_text: str, available_keys: list[str], available_artifacts: list[str]) -> dict[str, Any]:
	"""Call Ollama for intent parsing. Use cache to avoid repeated calls for same input."""
	if user_text in OLLAMA_CACHE:
		return OLLAMA_CACHE[user_text]
	
	prompt = (
		"You are an intent parser for a circuit generator. "
		"Return only strict JSON.\n"
		"Schema: {\"circuit\": string|null, \"direction\": \"forward\"|\"backward\"|null, "
		"\"provided_params\": object, \"ask\": string|null}.\n"
		f"Available circuits: {', '.join(sorted(available_keys))}.\n"
		f"Available model artifacts: {', '.join(sorted(available_artifacts))}.\n"
		"Rules:\n"
		"- Map synonyms/keywords to one available circuit.\n"
		"- If user gives an artifact name (example: B_xor or full_wave_rectifier_model), map it to the circuit key.\n"
		"- direction=forward when user gives component/input values and asks output.\n"
		"- direction=backward when user specifies OUTPUT VALUES (e.g., Y0=1, Y1=0, Vout=5.2) --> ALWAYS backward.\n"
		"- Extract obvious numeric parameters with their names into provided_params.\n"
		"- If unknown, set circuit to null and provide ask question.\n"
		f"User request: {user_text}\n"
	)

	payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
	try:
		response = requests.post(OLLAMA_URL, json=payload, timeout=30)
		response.raise_for_status()
		raw = response.json().get("response", "").strip()

		try:
			result = json.loads(raw)
		except json.JSONDecodeError:
			match = re.search(r"\{[\s\S]*\}", raw)
			if not match:
				raise
			result = json.loads(match.group(0))
		
		OLLAMA_CACHE[user_text] = result
		return result
	except Exception:
		# If Ollama fails, return safe defaults
		return {"circuit": None, "direction": None, "provided_params": {}, "ask": None}


def keyword_match(text: str, aliases: dict[str, str]) -> str | None:
	normalized = normalize_key(text)
	if normalized in aliases:
		candidate = aliases[normalized]
		if candidate in {"and", "or", "not"} and not logic_gate_context_present(text, candidate):
			return None
		return candidate

	words = normalized.split("_")
	for i in range(len(words), 0, -1):
		probe = "_".join(words[:i])
		if probe in aliases:
			return aliases[probe]

	for alias, key in aliases.items():
		if alias in {"and", "or", "not"} and not logic_gate_context_present(text, alias):
			continue
		if alias and alias in normalized:
			return key
	return None


def _word_tokens(text: str) -> set[str]:
	return {t for t in normalize_key(text).split("_") if t}


def fuzzy_circuit_match(user_text: str, all_keys: list[str], aliases: dict[str, str]) -> str | None:
	"""Best-effort topology matching for natural language and minor naming errors."""
	norm_text = normalize_key(user_text)
	if not norm_text:
		return None

	text_tokens = _word_tokens(norm_text)
	stopwords = {
		"design", "circuit", "with", "for", "the", "a", "an", "please", "make",
		"create", "build", "show", "draw", "find", "need", "values", "of",
	}
	text_tokens = {t for t in text_tokens if t not in stopwords}

	candidates: list[tuple[int, float, str]] = []
	for key in all_keys:
		k = normalize_key(key)
		k_tokens = _word_tokens(k)
		if not k_tokens:
			continue

		overlap = len(k_tokens & text_tokens)
		coverage = overlap / max(len(k_tokens), 1)
		sim = difflib.SequenceMatcher(a=norm_text, b=k).ratio()

		bonus = 0
		if k in norm_text:
			bonus += 2
		if overlap > 0 and k_tokens.issubset(text_tokens):
			bonus += 2

		score = (overlap + bonus, coverage + sim, key)
		candidates.append(score)

	if not candidates:
		return None

	sorted_candidates = sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)
	best = sorted_candidates[0]
	overlap_score, quality, picked = best
	second = sorted_candidates[1] if len(sorted_candidates) > 1 else None
	second_overlap = second[0] if second else -1
	second_quality = second[1] if second else -1.0

	# Conservative threshold to avoid random false positives.
	if overlap_score >= 2 or quality >= 1.15:
		if picked in {"and", "or", "not"} and not logic_gate_context_present(user_text, picked):
			return None
		return picked

	# Allow short natural inputs (e.g., "log") when there is a clear winner.
	if overlap_score >= 1 and (quality >= 0.80):
		clear_gap = (overlap_score > second_overlap) or ((quality - second_quality) >= 0.25)
		if clear_gap:
			if picked in {"and", "or", "not"} and not logic_gate_context_present(user_text, picked):
				return None
			return picked

	# Final fallback: fuzzy match against alias strings.
	alias_keys = list(aliases.keys())
	if alias_keys:
		match = difflib.get_close_matches(norm_text, alias_keys, n=1, cutoff=0.86)
		if match:
			picked_alias = match[0]
			picked_key = aliases.get(picked_alias)
			if picked_key in {"and", "or", "not"} and not logic_gate_context_present(user_text, picked_key):
				return None
			return picked_key

	return None


# Common output column names by domain
OUTPUT_COLUMN_NAMES = {
	"digital": {"y", "y0", "y1", "y2", "y3", "sum", "carry", "borrow", "valid", "out", "output"},
	"analog": {"vout", "v_out", "output_voltage", "vce", "vds", "valid"},
}

def infer_direction(user_text: str, provided: dict[str, Any] = None, domain_hint: str = "unknown") -> str:
	"""Improved direction inference with output parameter detection."""
	if provided is None:
		provided = {}
	
	lower = user_text.lower()
	backward_hints = ["design", "find", "required", "need values", "choose", "target", "desired"]
	
	# Check if user explicitly mentioned output/result parameters via VALUES
	provided_keys = {normalize_key(k) for k in provided.keys()}
	output_names = OUTPUT_COLUMN_NAMES.get(domain_hint, set())
	
	# ONLY backward if user provides OUTPUT VALUES (not just mentions the word "output")
	# E.g., "Y0=1" or "Vout=5.2" → backward, but "what's the output" is still forward
	if provided_keys & output_names:
		return "backward"
	
	# Fallback to keyword heuristic (but only real backward-intent words, not "output")
	if any(h in lower for h in backward_hints):
		return "backward"
	return "forward"


def classify_circuit_domain_from_key(circuit_key: str) -> str:
	k = normalize_key(circuit_key)
	# Some analog circuits also start with half_/full_ (e.g., rectifiers),
	# so handle analog-specific tokens before generic digital prefix checks.
	analog_tokens = {
		"rectifier",
		"amplifier",
		"integrator",
		"differentiator",
		"lowpass",
		"highpass",
		"bandpass",
		"inverting",
		"follower",
		"clamper",
		"clipper",
		"cb",
		"cc",
		"ce",
		"cd",
		"cg",
		"cs",
	}
	if any(token in k for token in analog_tokens):
		return "analog"

	if (
		k in DIGITAL_CIRCUIT_HINTS
		or k.endswith("_gate")
		or k.startswith("full_")
		or k.startswith("half_")
		or k.endswith("_counter")
	):
		return "digital"
	return "analog"


def classify_request_domain(user_text: str, provided: dict[str, Any]) -> str:
	text = normalize_key(user_text)
	parts = set(text.split("_"))
	provided_keys = {normalize_key(k) for k in provided.keys()}

	digital_score = 0
	analog_score = 0

	for word in parts | provided_keys:
		if word in DIGITAL_KEYWORDS:
			digital_score += 1
		if word in ANALOG_KEYWORDS:
			analog_score += 1

	# Strong analog hints from common specs.
	if any("voltage" in k or k in {"vin", "vout", "vcc", "vdd"} for k in provided_keys):
		analog_score += 2
	if any("frequency" in k or k in {"fh", "fl", "fc", "bw"} for k in provided_keys):
		analog_score += 2

	# Strong digital hints from logic symbols.
	if provided_keys & {"a", "b", "cin", "bin", "sum", "carry", "borrow", "y"}:
		digital_score += 1

	if analog_score > digital_score:
		return "analog"
	if digital_score > analog_score:
		return "digital"
	return "unknown"


def semantic_aliases_for_param(key: str) -> set[str]:
	k = normalize_key(key)
	aliases = {k}

	if "input" in k and "voltage" in k:
		aliases |= {"vin", "v_in", "input_voltage", "vcc", "vdd"}
	if "output" in k and "voltage" in k:
		aliases |= {"vout", "v_out", "output_voltage", "vce", "vds"}
	if "frequency" in k:
		aliases |= {"frequency", "fh", "fl", "fc", "cutoff_frequency", "output_frequency", "bw"}
	if "gain" in k:
		aliases |= {"gain", "av"}
	if "current" in k:
		aliases |= {"current", "ic", "ie", "id"}

	if k in {"vin", "v_in", "vcc", "vdd"}:
		aliases |= {"input_voltage"}
	if k in {"vout", "v_out", "vce", "vds"}:
		aliases |= {"output_voltage"}
	if k in {"fh", "fl", "fc", "bw"}:
		aliases |= {"frequency", "output_frequency", "cutoff_frequency"}
	if k == "av":
		aliases |= {"gain"}
	if k in {"ic", "collector_current"}:
		aliases |= {"ie", "emitter_current", "current"}
	if k in {"ie", "emitter_current"}:
		aliases |= {"ic", "collector_current", "current"}

	# Handle user typo from sample: kH/KH etc still maps to frequency key upstream.
	if "kh" in k:
		aliases |= {"frequency"}

	return {normalize_key(a) for a in aliases}


def overlap_score(required_fields: set[str], provided_fields: set[str]) -> int:
	score = 0
	for req in required_fields:
		req_aliases = semantic_aliases_for_param(req)
		for prov in provided_fields:
			prov_aliases = semantic_aliases_for_param(prov)
			if req_aliases & prov_aliases:
				score += 1
				break
	return score


def map_provided_to_required(
	required: list[str],
	provided: dict[str, Any],
) -> tuple[dict[str, float], list[str]]:
	"""Map user-provided params to required model inputs using semantic aliases."""
	accepted: dict[str, float] = {}
	consumed_keys: set[str] = set()

	normalized_provided: dict[str, Any] = {}
	for k, v in provided.items():
		nk = normalize_key(k)
		if nk and nk not in normalized_provided:
			normalized_provided[nk] = v

	for req in required:
		req_aliases = semantic_aliases_for_param(req)
		for pk, pv in normalized_provided.items():
			if pk in consumed_keys:
				continue
			if req_aliases & semantic_aliases_for_param(pk):
				try:
					accepted[req] = float(pv)
					consumed_keys.add(pk)
				except Exception:
					pass
				break

	invalid = sorted(k for k in normalized_provided.keys() if k not in consumed_keys)
	return accepted, invalid


def extract_numeric_params_from_text(text: str) -> dict[str, float]:
	params: dict[str, float] = {}

	# Generic key=value or key:value patterns (single-token key, avoids greedy phrase capture).
	for match in re.finditer(r"\b([a-zA-Z][a-zA-Z0-9_]*)\b\s*[:=]\s*(-?\d+(?:\.\d+)?)", text):
		name = normalize_key(match.group(1))
		if not name:
			continue
		try:
			params[name] = float(match.group(2))
		except ValueError:
			continue

	# Common engineering phrases.
	phrase_pattern = (
		r"(input voltage|output voltage|frequency|cutoff frequency|gain|vin|vout|av|fh|fl|bw|y0|y1|y2|y3|sum|carry|borrow|valid)"
		r"\s*(?:is|=|:|of)?\s*(-?\d+(?:\.\d+)?)\s*(?:[a-zA-Z%]+)?"
	)
	for match in re.finditer(phrase_pattern, text, flags=re.IGNORECASE):
		name = normalize_key(match.group(1))
		try:
			params[name] = float(match.group(2))
		except ValueError:
			continue

	# Canonical aliases for scoring.
	if "vin" in params:
		params.setdefault("input_voltage", params["vin"])
	if "vout" in params:
		params.setdefault("output_voltage", params["vout"])

	return params


def logic_gate_context_present(user_text: str, key: str) -> bool:
	lower = user_text.lower()
	if lower.strip() == key:
		return True
	if re.search(rf"\b{re.escape(key)}\s+gate\b", lower):
		return True
	if any(h in lower for h in ("logic", "boolean", "truth table")):
		return True
	return False


def heuristic_circuit_from_text(user_text: str) -> str | None:
	t = normalize_key(user_text)
	if any(k in t for k in ("rc_highpass", "rc_high_pass", "rc_hpf", "high_pass_filter")):
		return "rc_highpass"
	if any(k in t for k in ("rl_highpass", "rl_high_pass", "rl_hpf")):
		return "rl_highpass"
	if any(k in t for k in ("rl_lowpass", "rl_low_pass", "rl_lpf")):
		return "rl_lowpass"
	if any(k in t for k in ("rlc_parallel_bandpass", "tlc_parallel_bandpass", "parallel_bandpass")):
		return "rlc_parallel_bandpass"
	if any(k in t for k in ("rlc_series_bandpass", "series_bandpass")):
		return "rlc_series_bandpass"
	if any(k in t for k in ("low_pass", "lowpass", "lpf", "rc_lpf", "low_pass_filter")):
		return "rc_lpf"
	if any(k in t for k in ("non_inverting", "noninverting", "non_invering", "noninvering", "non_invert")):
		return "non_inverting"
	if "inverting" in t:
		return "inverting"
	if "integrator" in t:
		return "integrator"
	if "differentiator" in t:
		return "differentiator"
	if "common_emitter" in t:
		return "ce"
	if "common_base" in t:
		return "cb"
	if "common_collector" in t:
		return "cc"
	return None

def heuristic_circuit_from_params(provided: dict[str, Any]) -> str | None:
	keys = {normalize_key(k) for k in provided.keys()}
	if {"input_voltage", "output_voltage"}.issubset(keys) and (
		"frequency" in keys or "cutoff_frequency" in keys
	):
		return "rc_lpf"
	return None


def circuit_candidate_is_reliable(circuit_key: str, user_text: str, domain_hint: str) -> bool:
	ck = normalize_key(circuit_key)
	if ck in {"and", "or", "not"} and not logic_gate_context_present(user_text, ck):
		return False
	if domain_hint in ("analog", "digital") and classify_circuit_domain_from_key(ck) != domain_hint:
		return False
	return True


def infer_io_fields(
	choice: ModelChoice,
	dataset_cols: list[str] | None,
) -> tuple[list[str], list[str]]:
	model = load_model(choice.path)

	feature_names = list(getattr(model, "feature_names_in_", []))
	n_features = int(getattr(model, "n_features_in_", len(feature_names) or 0))
	is_generic_feature_space = bool(feature_names) and all(
		re.fullmatch(r"x\d+", normalize_key(str(name))) is not None for name in feature_names
	)

	if feature_names and not is_generic_feature_space:
		inputs = feature_names
	elif dataset_cols and n_features > 0 and len(dataset_cols) >= n_features:
		ck = normalize_key(choice.key)
		priorities = ANALOG_PARAM_PRIORITIES.get(ck, {}).get(choice.direction, [])

		if priorities:
			picked: list[str] = []
			by_norm = {normalize_key(c): c for c in dataset_cols}
			for p in priorities:
				resolved = by_norm.get(normalize_key(p))
				if resolved and resolved not in picked:
					picked.append(resolved)

			for c in dataset_cols:
				if c not in picked:
					picked.append(c)

			inputs = picked[:n_features]
		elif choice.direction == "backward":
			inputs = dataset_cols[-n_features:]
		else:
			inputs = dataset_cols[:n_features]
	else:
		inputs = [f"x{i + 1}" for i in range(max(n_features, 1))]

	outputs: list[str] = []
	if dataset_cols:
		outputs = [c for c in dataset_cols if c not in inputs]

	return inputs, outputs


def to_float(value: str) -> float:
	return float(value.strip())


def load_default_values_from_dataset(circuit_key: str, dataset_cols: dict[str, list[str]]) -> dict[str, float]:
	"""Load median/default values from dataset CSV for non-critical parameters."""
	defaults: dict[str, float] = {}
	ck = normalize_key(circuit_key)
	dataset_dir = BASE_DIR / "datasets"

	def path_score(csv_path: Path) -> tuple[int, int]:
		dk = dataset_key_from_stem(csv_path.stem)
		if dk == ck:
			return (100, 0)

		ck_tokens = set(ck.split("_")) if ck else set()
		dk_tokens = set(dk.split("_")) if dk else set()
		overlap = len(ck_tokens & dk_tokens)
		substring_boost = 10 if (ck and (ck in dk or dk in ck)) else 0
		# Prefer closer names when overlap ties.
		distance = abs(len(dk) - len(ck))
		return (overlap * 3 + substring_boost, -distance)

	best_path: Path | None = None
	best_score = (-1, -10_000)
	for csv_path in dataset_dir.rglob("*.csv"):
		score = path_score(csv_path)
		if score > best_score:
			best_score = score
			best_path = csv_path

	# Require at least some similarity to avoid random dataset picks.
	if best_path is None or best_score[0] <= 0:
		return defaults

	try:
		df = pd.read_csv(best_path)
		for col in df.columns:
			norm_col = normalize_key(col)
			if pd.api.types.is_numeric_dtype(df[col]):
				defaults[norm_col] = float(df[col].median())
	except Exception:
		return {}

	return defaults


def load_global_defaults_from_all_datasets() -> dict[str, float]:
	"""Global per-parameter medians across all datasets as fallback defaults."""
	global GLOBAL_DEFAULTS_CACHE
	if GLOBAL_DEFAULTS_CACHE is not None:
		return GLOBAL_DEFAULTS_CACHE

	agg: dict[str, list[float]] = {}
	for csv_path in DATASET_DIR.rglob("*.csv"):
		try:
			df = pd.read_csv(csv_path)
		except Exception:
			continue
		for col in df.columns:
			if not pd.api.types.is_numeric_dtype(df[col]):
				continue
			vals = pd.to_numeric(df[col], errors="coerce").dropna()
			if vals.empty:
				continue
			norm_col = normalize_key(col)
			agg.setdefault(norm_col, []).extend(vals.astype(float).tolist())

	GLOBAL_DEFAULTS_CACHE = {}
	for k, vals in agg.items():
		if vals:
			GLOBAL_DEFAULTS_CACHE[k] = float(np.median(np.array(vals, dtype=float)))

	return GLOBAL_DEFAULTS_CACHE


def resolve_default_value(param_name: str, circuit_defaults: dict[str, float]) -> float | None:
	"""Resolve defaults using exact key, semantic aliases, global medians, then priors."""
	pk = normalize_key(param_name)
	if pk in circuit_defaults:
		return float(circuit_defaults[pk])

	p_aliases = semantic_aliases_for_param(pk)
	for dk, dv in circuit_defaults.items():
		if p_aliases & semantic_aliases_for_param(dk):
			return float(dv)

	global_defaults = load_global_defaults_from_all_datasets()
	if pk in global_defaults:
		return float(global_defaults[pk])

	for gk, gv in global_defaults.items():
		if p_aliases & semantic_aliases_for_param(gk):
			return float(gv)

	if pk in COMMON_PARAMETER_DEFAULTS:
		return float(COMMON_PARAMETER_DEFAULTS[pk])

	for ck, cv in COMMON_PARAMETER_DEFAULTS.items():
		if p_aliases & semantic_aliases_for_param(ck):
			return float(cv)

	return None


def load_dataset_frame(circuit_key: str) -> pd.DataFrame | None:
	"""Load the full dataset frame for a circuit key, if available."""
	dataset_dir = BASE_DIR / "datasets"
	for csv_path in dataset_dir.rglob("*.csv"):
		if dataset_key_from_stem(csv_path.stem) == circuit_key:
			try:
				return pd.read_csv(csv_path)
			except Exception:
				continue
	return None


def identify_critical_params(circuit_key: str, domain: str) -> set[str]:
	"""Identify which parameters are critical inputs vs. non-critical settings."""
	# For digital circuits: D inputs, A/B inputs are critical; propagation delay, supply voltage, temperature are non-critical
	# For analog circuits: Vin, component values are critical; temperature, supply voltage are non-critical
	critical_digital = {"d0", "d1", "d2", "d3", "a", "b", "cin", "bin"}
	
	ck = normalize_key(circuit_key)
	if ck in DIGITAL_CIRCUIT_HINTS:
		return critical_digital
	
	# For analog: usually first few params are critical
	return set()


def normalize_digital_values(
	inputs: dict[str, float],
	outputs: dict[str, float],
	circuit_key: str,
) -> tuple[dict[str, float], dict[str, float]]:
	"""Convert digital circuit parameters to binary (0 or 1) values.
	
	For digital circuits, binary input/output parameters should be 0 or 1,
	not floating-point values like 0.5. This function normalizes them.
	"""
	ck = normalize_key(circuit_key)
	
	# Check if circuit is digital - check base names and patterns
	is_digital = False
	
	# Check against DIGITAL_CIRCUIT_HINTS (handles "and", "or", "nand", "nor", etc.)
	if ck in DIGITAL_CIRCUIT_HINTS:
		is_digital = True
	# Handle gate circuits: "and_gate" should match "and" in hints
	elif any(kw in ck for kw in {"and", "or", "not", "nand", "nor", "xor", "xnor"}):
		is_digital = True
	# Handle adders, subtractors, etc.
	elif any(pat in ck for pat in {"adder", "subtractor", "comparator", "mux", "demux", "encoder", "decoder", "counter", "priority"}):
		is_digital = True
	
	if not is_digital:
		return inputs, outputs
	
	# Binary input parameter names (logic inputs)
	binary_input_params = {"a", "b", "c", "d", "d0", "d1", "d2", "d3", "cin", "bin", "clk", "en", "rst"}
	
	# Binary output parameter names (logic outputs)
	binary_output_params = {"y", "y0", "y1", "y2", "y3", "sum", "carry", "borrow", "cout", "valid", "out", "output"}
	
	# Normalize input values
	normalized_inputs = {}
	for key, value in inputs.items():
		nk = normalize_key(key)
		if nk in binary_input_params:
			# Convert float to binary: round to nearest 0 or 1
			normalized_inputs[key] = float(1 if value >= 0.5 else 0)
		else:
			normalized_inputs[key] = value
	
	# Normalize output values
	normalized_outputs = {}
	for key, value in outputs.items():
		nk = normalize_key(key)
		if nk in binary_output_params:
			# Convert float to binary: round to nearest 0 or 1
			normalized_outputs[key] = float(1 if value >= 0.5 else 0)
		else:
			normalized_outputs[key] = value
	
	return normalized_inputs, normalized_outputs


def collect_missing_params(
	required: list[str],
	provided: dict[str, Any],
	circuit_key: str = "",
	dataset_cols: dict[str, list[str]] | None = None,
	force_prompt: bool = False,
	allow_autofill: bool = True,
) -> tuple[dict[str, float], list[str]]:
	"""Collect required parameters with dataset defaults and interactive fallback."""
	if dataset_cols is None:
		dataset_cols = {}

	values: dict[str, float] = {}
	auto_filled: list[str] = []

	mapped, _ = map_provided_to_required(required, provided)
	
	# Load defaults for dataset-backed autofill.
	try:
		defaults = load_default_values_from_dataset(circuit_key, dataset_cols)
	except Exception:
		defaults = {}

	# Seed from provided values first.
	for param, val in mapped.items():
		values[param] = val

	if force_prompt:
		print("\nEnter your desired values (press Enter to keep the shown default/current value).")
		for param in required:
			if param in values:
				default_val = values[param]
			else:
				default_val = resolve_default_value(param, defaults)

			if default_val is not None:
				values[param] = default_val
				auto_filled.append(param)

			while True:
				try:
					prompt = f"Enter {param}"
					if default_val is not None:
						prompt += f" [default {default_val}]"
					prompt += ": "
					raw = input(prompt).strip()
				except EOFError:
					raw = ""

				if raw == "" and default_val is not None:
					values[param] = float(default_val)
					break
				if raw == "":
					print("A value is required because no default is available.")
					continue
				try:
					values[param] = to_float(raw)
					break
				except ValueError:
					print("Please enter a numeric value.")
		return values, auto_filled

	missing_required = [p for p in required if p not in values]
	if not missing_required:
		return values, auto_filled

	print("\nMissing required parameters: " + ", ".join(missing_required))
	try:
		confirm = input("Do you want to provide them now? (y/n): ").strip().lower()
	except EOFError:
		confirm = "n"

	if confirm == "y":
		for param in missing_required:
			default_val = resolve_default_value(param, defaults)
			while True:
				try:
					prompt = f"Enter {param}"
					if default_val is not None:
						prompt += f" [default {default_val}]"
					prompt += ": "
					raw = input(prompt).strip()
				except EOFError:
					raw = ""

				if raw == "" and default_val is not None:
					values[param] = float(default_val)
					if param not in auto_filled:
						auto_filled.append(param)
					break
				if raw == "":
					print("A value is required because no default is available.")
					continue
				try:
					values[param] = to_float(raw)
					break
				except ValueError:
					print("Please enter a numeric value.")
	else:
		still_missing: list[str] = []
		for param in missing_required:
			default_val = resolve_default_value(param, defaults) if allow_autofill else None
			if default_val is not None:
				values[param] = default_val
				if param not in auto_filled:
					auto_filled.append(param)
			else:
				still_missing.append(param)

		if auto_filled:
			print(
				"You did not provide some required parameters, so dataset defaults were used for: "
				+ ", ".join(auto_filled)
			)

		if still_missing:
			print(
				"No dataset defaults found for: "
				+ ", ".join(still_missing)
				+ ". Please enter these values to continue."
			)
			for param in still_missing:
				while True:
					try:
						raw = input(f"Enter {param}: ").strip()
					except EOFError:
						print("Input stream ended while required values are still missing.")
						raise SystemExit(1)
					try:
						values[param] = to_float(raw)
						break
					except ValueError:
						print("Please enter a numeric value.")

	return values, auto_filled


def run_prediction(choice: ModelChoice, ordered_inputs: list[str], values: dict[str, float]) -> np.ndarray:
	model = load_model(choice.path)
	missing = [name for name in ordered_inputs if name not in values]
	if missing:
		raise ValueError("Missing required input values: " + ", ".join(missing))
	row = [values[name] for name in ordered_inputs]
	# Use ndarray to avoid strict feature-name coupling for legacy models that expose x1/x2/... names.
	pred = model.predict(np.array([row], dtype=float))
	arr = np.array(pred)
	if arr.ndim == 0:
		return arr.reshape(1)
	if arr.ndim == 1:
		return arr
	return arr[0]


def model_looks_insensitive(
	choice: ModelChoice,
	ordered_inputs: list[str],
	values: dict[str, float],
	base_prediction: np.ndarray,
) -> bool:
	"""Heuristic: check if model prediction changes under a noticeable input perturbation."""
	if not ordered_inputs:
		return False

	trial_values = dict(values)
	for name in ordered_inputs:
		v = float(trial_values[name])
		# Apply a strong but reasonable perturbation to expose constant-output models.
		if abs(v) < 1e-9:
			trial_values[name] = 1.0
		else:
			trial_values[name] = v * 1.2

	try:
		trial_prediction = run_prediction(choice, ordered_inputs, trial_values)
	except Exception:
		return False

	return np.allclose(np.array(base_prediction, dtype=float), np.array(trial_prediction, dtype=float), rtol=1e-9, atol=1e-9)


def dataset_nearest_fallback_prediction(
	circuit_key: str,
	required_inputs: list[str],
	output_names: list[str],
	values: dict[str, float],
) -> np.ndarray | None:
	"""Fallback prediction by nearest-neighbor lookup in circuit dataset."""
	df = load_dataset_frame(circuit_key)
	if df is None or df.empty:
		return None

	input_cols = [c for c in required_inputs if c in df.columns]
	if len(input_cols) != len(required_inputs):
		return None

	if not output_names:
		return None
	out_cols = [c for c in output_names if c in df.columns]
	if len(out_cols) != len(output_names):
		return None

	work = df.dropna(subset=input_cols + out_cols)
	if work.empty:
		return None

	try:
		target = np.array([float(values[c]) for c in input_cols], dtype=float)
		x = work[input_cols].to_numpy(dtype=float)
		dists = np.linalg.norm(x - target, axis=1)
		idx = int(np.argmin(dists))
		best_row = work.iloc[idx]
		return np.array([float(best_row[c]) for c in out_cols], dtype=float)
	except Exception:
		return None


def detect_intent(
	user_text: str,
	catalog: dict[str, dict[str, Path]],
	aliases: dict[str, str],
	inventory: dict[str, list[Path]],
) -> tuple[str | None, str, dict[str, Any], str | None]:
	"""Detect user intent with improved heuristics. Only call Ollama as fallback."""
	all_keys = sorted(set(catalog["forward"].keys()) | set(catalog["backward"].keys()))
	all_artifacts = [p.stem for p in inventory["forward"] + inventory["backward"]]
	local_circuit = keyword_match(user_text, aliases)
	if not local_circuit:
		local_circuit = fuzzy_circuit_match(user_text, all_keys, aliases)
	heuristic_circuit = heuristic_circuit_from_text(user_text)
	base_provided = extract_numeric_params_from_text(user_text)
	param_heuristic_circuit = heuristic_circuit_from_params(base_provided)
	domain_hint = classify_request_domain(user_text, base_provided)

	# Try deterministic methods first before expensive Ollama call
	circuit = param_heuristic_circuit or heuristic_circuit or local_circuit
	if circuit and circuit_candidate_is_reliable(circuit, user_text, domain_hint):
		direction = infer_direction(user_text, base_provided, domain_hint)
		return circuit, direction, base_provided, None

	# Only call Ollama if heuristics didn't work
	try:
		parsed = call_ollama_for_intent(user_text, all_keys, all_artifacts)
		circuit = parsed.get("circuit")
		direction = parsed.get("direction") or infer_direction(user_text, base_provided, domain_hint)
		provided = parsed.get("provided_params") or {}
		ask = parsed.get("ask")

		if isinstance(circuit, str):
			circuit = normalize_key(circuit)
		else:
			circuit = None

		if circuit and circuit not in all_keys:
			circuit = keyword_match(circuit, aliases)

		if not isinstance(provided, dict):
			provided = {}

		# Augment with deterministic extraction
		extracted = base_provided
		for k, v in extracted.items():
			provided.setdefault(k, v)

		# Deterministic direction guard: output-value requests must stay backward.
		deterministic_direction = infer_direction(user_text, provided, domain_hint)
		if deterministic_direction == "backward":
			direction = "backward"

		# Prefer deterministic circuit cues over LLM matches
		if param_heuristic_circuit and param_heuristic_circuit in all_keys:
			circuit = param_heuristic_circuit
		elif heuristic_circuit and heuristic_circuit in all_keys:
			circuit = heuristic_circuit
		elif circuit and not circuit_candidate_is_reliable(circuit, user_text, domain_hint):
			circuit = None

		if not circuit:
			circuit = local_circuit
		if circuit and not circuit_candidate_is_reliable(circuit, user_text, domain_hint):
			circuit = None

		return circuit, direction, provided, ask
	except Exception:
		circuit = param_heuristic_circuit or heuristic_circuit or local_circuit
		if circuit and not circuit_candidate_is_reliable(circuit, user_text, domain_hint):
			circuit = None
		direction = infer_direction(user_text, base_provided, domain_hint)
		provided = base_provided
		return circuit, direction, provided, None


def wants_model_inventory(user_text: str) -> bool:
	needle = normalize_key(user_text)
	hints = (
		"list_models",
		"show_models",
		"available_models",
		"what_models",
		"model_list",
		"inventory",
	)
	return any(h in needle for h in hints)


def print_model_inventory(inventory: dict[str, list[Path]]) -> None:
	print("\nDiscovered models:")
	for direction in ("forward", "backward"):
		items = inventory[direction]
		print(f"- {direction.title()} ({len(items)}):")
		if not items:
			print("  (none)")
			continue
		for p in items:
			print(f"  - {p.stem}")


def to_bit(value: Any) -> int | None:
	try:
		v = int(round(float(value)))
	except Exception:
		return None
	if v in (0, 1):
		return v
	return None


def truth_table_eval(circuit_key: str, bits: dict[str, int]) -> dict[str, int] | None:
	a = bits.get("a")
	b = bits.get("b")
	cin = bits.get("cin")
	bin_ = bits.get("bin")

	if circuit_key == "and" and a is not None and b is not None:
		return {"y": a & b}
	if circuit_key == "or" and a is not None and b is not None:
		return {"y": a | b}
	if circuit_key == "not" and a is not None:
		return {"y": 1 - a}
	if circuit_key == "nand" and a is not None and b is not None:
		return {"y": 1 - (a & b)}
	if circuit_key == "nor" and a is not None and b is not None:
		return {"y": 1 - (a | b)}
	if circuit_key == "xor" and a is not None and b is not None:
		return {"y": a ^ b}
	if circuit_key == "xnor" and a is not None and b is not None:
		return {"y": 1 - (a ^ b)}
	if circuit_key == "half_adder" and a is not None and b is not None:
		return {"sum": a ^ b, "carry": a & b}
	if circuit_key == "full_adder" and a is not None and b is not None and cin is not None:
		s = a ^ b ^ cin
		c = (a & b) | (b & cin) | (a & cin)
		return {"sum": s, "carry": c}
	if circuit_key == "half_subtractor" and a is not None and b is not None:
		d = a ^ b
		br = (1 - a) & b
		return {"diff": d, "borrow": br}
	if circuit_key == "full_subtractor" and a is not None and b is not None and bin_ is not None:
		d = a ^ b ^ bin_
		br = ((1 - a) & b) | ((1 - a) & bin_) | (b & bin_)
		return {"diff": d, "borrow": br}
	if circuit_key == "comparator" and a is not None and b is not None:
		return {
			"a_gt_b": int(a > b),
			"a_eq_b": int(a == b),
			"a_lt_b": int(a < b),
		}
	return None


def canonical_digital_key(circuit_key: str) -> str:
	"""Normalize topology aliases to canonical truth-table keys."""
	ck = normalize_key(circuit_key)
	if ck.endswith("_gate"):
		base = ck[: -len("_gate")]
		if base in {"and", "or", "not", "nand", "nor", "xor", "xnor"}:
			return base
	return ck


def override_digital_outputs_for_display(
	circuit_key: str,
	inputs: dict[str, float],
	outputs: dict[str, float],
) -> dict[str, float]:
	"""For supported digital circuits, align displayed outputs with truth table from shown inputs."""
	canonical_key = canonical_digital_key(circuit_key)
	
	# Convert known input keys to bits for truth-table evaluation.
	input_bits: dict[str, int] = {}
	for k, v in inputs.items():
		nk = normalize_key(k)
		bv = to_bit(v)
		if bv is None:
			continue
		if nk in {"a", "b", "cin", "bin"}:
			input_bits[nk] = bv

	truth = truth_table_eval(canonical_key, input_bits)
	if not truth:
		return outputs

	patched = dict(outputs)
	for out_key, out_val in list(patched.items()):
		nk = normalize_key(out_key)
		if nk in truth:
			patched[out_key] = float(truth[nk])

	return patched


def prompt_missing_bits(required: list[str], given: dict[str, int]) -> dict[str, int]:
	out = dict(given)
	for k in required:
		if k in out:
			continue
		while True:
			raw = input(f"Enter {k} (0 or 1): ").strip()
			bv = to_bit(raw)
			if bv is None:
				print("Please enter 0 or 1.")
				continue
			out[k] = bv
			break
	return out


def maybe_run_rule_based_digital(circuit_key: str, user_text: str, provided: dict[str, Any]) -> bool:
	if classify_circuit_domain_from_key(circuit_key) != "digital":
		return False

	norm = {normalize_key(k): v for k, v in provided.items()}
	bits = {k: to_bit(v) for k, v in norm.items()}
	bits = {k: v for k, v in bits.items() if v is not None}

	req_inputs_map = {
		"and": ["a", "b"],
		"or": ["a", "b"],
		"not": ["a"],
		"nand": ["a", "b"],
		"nor": ["a", "b"],
		"xor": ["a", "b"],
		"xnor": ["a", "b"],
		"half_adder": ["a", "b"],
		"full_adder": ["a", "b", "cin"],
		"half_subtractor": ["a", "b"],
		"full_subtractor": ["a", "b", "bin"],
		"comparator": ["a", "b"],
	}

	req_outputs_map = {
		"and": ["y"],
		"or": ["y"],
		"not": ["y"],
		"nand": ["y"],
		"nor": ["y"],
		"xor": ["y"],
		"xnor": ["y"],
		"half_adder": ["sum", "carry"],
		"full_adder": ["sum", "carry"],
		"half_subtractor": ["diff", "borrow"],
		"full_subtractor": ["diff", "borrow"],
		"comparator": ["a_gt_b", "a_eq_b", "a_lt_b"],
	}

	if circuit_key not in req_inputs_map:
		return False

	req_inputs = req_inputs_map[circuit_key]
	req_outputs = req_outputs_map[circuit_key]
	input_bits = {k: bits[k] for k in req_inputs if k in bits}
	output_bits = {k: bits[k] for k in req_outputs if k in bits}

	mode = infer_direction(user_text)
	if input_bits and not output_bits:
		mode = "forward"
	elif output_bits and not input_bits:
		mode = "backward"

	if mode == "forward":
		full_inputs = prompt_missing_bits(req_inputs, input_bits)
		result = truth_table_eval(circuit_key, full_inputs)
		if result is None:
			return False
		print("\nRule-based digital prediction:")
		for k in req_outputs:
			print(f"- {k}: {result[k]}")
		return True

	# Backward mode: brute-force all input combinations.
	targets = prompt_missing_bits(req_outputs, output_bits)
	candidates: list[dict[str, int]] = []
	for a in (0, 1):
		for b in (0, 1):
			for cin in (0, 1):
				for bin_ in (0, 1):
					trial = {"a": a, "b": b, "cin": cin, "bin": bin_}
					out = truth_table_eval(circuit_key, trial)
					if out is None:
						continue
					if all(out.get(k) == v for k, v in targets.items()):
						picked = {name: trial[name] for name in req_inputs}
						if picked not in candidates:
							candidates.append(picked)

	print("\nRule-based digital inverse solutions:")
	if not candidates:
		print("- No binary input combination satisfies the requested outputs.")
	else:
		for i, c in enumerate(candidates, start=1):
			print(f"- Solution {i}: " + ", ".join(f"{k}={v}" for k, v in c.items()))
	return True


def score_choice_by_params(
	choice: ModelChoice,
	provided: dict[str, Any],
	data_cols: dict[str, list[str]],
	direction_hint: str,
	domain_hint: str,
) -> tuple[int, int, int]:
	dataset_cols = dataset_cols_for_circuit(choice.key, data_cols)
	inputs, outputs = infer_io_fields(choice, dataset_cols)

	provided_keys = {normalize_key(k) for k in provided.keys()}
	input_keys = {normalize_key(k) for k in inputs}
	output_keys = {normalize_key(k) for k in outputs}

	in_matches = overlap_score(input_keys, provided_keys)
	out_matches = overlap_score(output_keys, provided_keys)

	# Prioritize matching required model inputs (so prediction can run directly).
	score = (3 * in_matches) + out_matches

	# If request references both sides of IO, boost candidates that explain both.
	if in_matches > 0 and out_matches > 0:
		score += 2

	# Prefer candidates that need fewer additional input parameters.
	missing_inputs = max(len(input_keys) - in_matches, 0)
	score -= missing_inputs
	if direction_hint in ("forward", "backward") and choice.direction == direction_hint:
		score += 1

	if domain_hint in ("analog", "digital"):
		if classify_circuit_domain_from_key(choice.key) == domain_hint:
			score += 3
		else:
			score -= 3

	# Tie-breakers: more input matches, then output matches.
	return score, in_matches, out_matches


def best_choice_for_circuit(
	circuit_key: str,
	direction_hint: str,
	catalog: dict[str, dict[str, Path]],
	data_cols: dict[str, list[str]],
	provided: dict[str, Any],
	domain_hint: str,
) -> ModelChoice | None:
	candidates: list[ModelChoice] = []
	for direction in ("forward", "backward"):
		path = catalog.get(direction, {}).get(circuit_key)
		if path:
			candidates.append(ModelChoice(circuit_key, direction, path))

	if not candidates:
		return None

	if not provided:
		# If no params are available, keep existing direction preference behavior.
		for c in candidates:
			if c.direction == direction_hint:
				return c
		return candidates[0]

	return max(
		candidates,
		key=lambda c: score_choice_by_params(c, provided, data_cols, direction_hint, domain_hint),
	)


def best_choice_from_all_models(
	direction_hint: str,
	catalog: dict[str, dict[str, Path]],
	data_cols: dict[str, list[str]],
	provided: dict[str, Any],
	domain_hint: str,
) -> ModelChoice | None:
	if not provided:
		return None

	candidates: list[ModelChoice] = []
	for direction in ("forward", "backward"):
		for key, path in catalog.get(direction, {}).items():
			candidates.append(ModelChoice(key, direction, path))

	if not candidates:
		return None

	scored = [
		(
			score_choice_by_params(c, provided, data_cols, direction_hint, domain_hint),
			c,
		)
		for c in candidates
	]
	scored.sort(key=lambda item: item[0], reverse=True)
	best_score_tuple, best = scored[0]
	best_score, in_matches, out_matches = best_score_tuple

	# If top candidates tie across different circuits, ask user instead of guessing.
	if len(scored) > 1:
		second_score_tuple, second = scored[1]
		if best_score_tuple == second_score_tuple and best.key != second.key:
			return None

	# Require a minimum confidence to avoid random model picks.
	if best_score < 2 and in_matches == 0 and out_matches == 0:
		return None
	return best


def run_intent_self_tests(
	catalog: dict[str, dict[str, Path]],
	data_cols: dict[str, list[str]],
	aliases: dict[str, str],
	inventory: dict[str, list[Path]],
) -> None:
	print("\nRunning intent self-tests...")
	tests = [
		"input voltage=5V output voltage=2V and output frequency is 5kH",
		"Design a common emitter with Av=20 and fH=100000",
		"Need XOR output for A=1 B=0",
		"Given Sum=1 Carry=0 find full adder inputs",
		"low pass filter with Vin=5, Vout=2, cutoff frequency=5000",
		"A=1 B=1 what is output",
		"Need comparator for A=3 B=5",
		"Find required values for inverting amplifier gain=10",
	]

	all_keys = sorted(set(catalog["forward"].keys()) | set(catalog["backward"].keys()))

	for i, query in enumerate(tests, start=1):
		circuit_key, direction, provided, _ = detect_intent(query, catalog, aliases, inventory)
		domain = classify_request_domain(query, provided)

		choice: ModelChoice | None
		if circuit_key and circuit_key in all_keys:
			choice = best_choice_for_circuit(circuit_key, direction, catalog, data_cols, provided, domain)
		else:
			choice = best_choice_from_all_models(direction, catalog, data_cols, provided, domain)

		picked = f"{pretty_label(choice.key)} ({choice.direction})" if choice else "None"
		print(f"[{i}] query: {query}")
		print(f"    parsed circuit={circuit_key}, direction={direction}, domain={domain}")
		print(f"    provided keys={sorted(normalize_key(k) for k in provided.keys())}")
		print(f"    selected={picked}")


def select_model(
	circuit_key: str,
	direction: str,
	catalog: dict[str, dict[str, Path]],
) -> ModelChoice | None:
	direction = direction if direction in ("forward", "backward") else "forward"

	path = catalog.get(direction, {}).get(circuit_key)
	if path:
		return ModelChoice(key=circuit_key, direction=direction, path=path)

	other = "backward" if direction == "forward" else "forward"
	path = catalog.get(other, {}).get(circuit_key)
	if path:
		print(f"{direction.title()} model not available for {pretty_label(circuit_key)}. Using {other} model.")
		return ModelChoice(key=circuit_key, direction=other, path=path)

	return None


def format_numeric_value(value: float) -> str:
	"""Format numbers for CLI output without hiding very small magnitudes."""
	v = float(value)
	if not np.isfinite(v):
		return str(v)

	# Keep whole-number outputs readable.
	if abs(v - round(v)) < 1e-9 and abs(v) >= 1:
		return str(int(round(v)))

	abs_v = abs(v)
	# Avoid printing tiny non-zero values as 0.000000.
	if (abs_v != 0.0 and abs_v < 1e-4) or abs_v >= 1e6:
		return f"{v:.6e}"

	s = f"{v:.12f}".rstrip("0").rstrip(".")
	if s in ("-0", ""):
		return "0"
	return s


def print_results(outputs: list[str], prediction: np.ndarray) -> None:
	pred_list = prediction.astype(float).flatten().tolist()

	if outputs and len(outputs) == len(pred_list):
		print("\nPredicted values:")
		for name, val in zip(outputs, pred_list):
			print(f"- {name}: {format_numeric_value(val)}")
	else:
		print("\nPredicted values:")
		for i, val in enumerate(pred_list, start=1):
			print(f"- y{i}: {format_numeric_value(val)}")


def infer_output_names_from_counterpart(
	choice: ModelChoice,
	catalog: dict[str, dict[str, Path]],
	pred_len: int,
) -> list[str]:
	other = "backward" if choice.direction == "forward" else "forward"
	counterpart = catalog.get(other, {}).get(choice.key)
	if not counterpart:
		return []

	model = load_model(counterpart)
	feature_names = list(getattr(model, "feature_names_in_", []))
	if len(feature_names) == pred_len:
		return feature_names
	return []


def main() -> None:
	parser = argparse.ArgumentParser(add_help=True)
	parser.add_argument("--self-test", action="store_true", help="Run built-in intent selection tests and exit.")
	args = parser.parse_args()

	catalog = discover_models()
	inventory = discover_model_inventory()
	data_cols = load_dataset_columns()
	aliases = alias_map(catalog, inventory)

	if not catalog["forward"] and not catalog["backward"]:
		print("No models found in models/models_forward or models/models_backward.")
		return

	print("Circuit Generator (Ollama + ML Models)")
	print("Type your goal, for example: 'Design a common emitter with Av=20 and fH=100000'.")
	print("Tip: type 'list models' to see every discovered forward/backward artifact.")

	if args.self_test:
		run_intent_self_tests(catalog, data_cols, aliases, inventory)
		return

	user_text = input("\nWhat circuit do you want to generate? ").strip()
	if not user_text:
		print("Empty request. Exiting.")
		return

	if wants_model_inventory(user_text):
		print_model_inventory(inventory)
		return

	circuit_key, direction, provided, ask = detect_intent(user_text, catalog, aliases, inventory)
	domain_hint = classify_request_domain(user_text, provided)
	print(f"Detected domain: {domain_hint}")

	choice: ModelChoice | None = None
	if circuit_key:
		choice = best_choice_for_circuit(circuit_key, direction, catalog, data_cols, provided, domain_hint)
		if choice and choice.direction != direction:
			print(
				f"Direction adjusted to {choice.direction} based on provided parameters "
				f"for {pretty_label(choice.key)}."
			)
	else:
		choice = best_choice_from_all_models(direction, catalog, data_cols, provided, domain_hint)
		if choice:
			print(
				"Circuit name not explicit; auto-selected "
				f"{pretty_label(choice.key)} ({choice.direction}) from parameter overlap."
			)

	while not choice:
		if ask:
			print(ask)
		else:
			print("I could not determine the circuit. Available circuits include:")
			all_keys = sorted(set(catalog["forward"].keys()) | set(catalog["backward"].keys()))
			print(", ".join(pretty_label(k) for k in all_keys))

		user_text = input("Please specify the circuit name: ").strip()
		circuit_key = keyword_match(user_text, aliases)
		if not circuit_key:
			circuit_key = normalize_key(user_text)
		if circuit_key in (set(catalog["forward"].keys()) | set(catalog["backward"].keys())):
			choice = select_model(circuit_key, direction, catalog)
		else:
			choice = None

	if not choice:
		print("No suitable model found for the request.")
		return

	if maybe_run_rule_based_digital(choice.key, user_text, provided):
		return

	dataset_cols = dataset_cols_for_circuit(choice.key, data_cols)
	required_inputs, known_outputs = infer_io_fields(choice, dataset_cols)

	print(f"\nSelected circuit: {pretty_label(choice.key)}")
	print(f"Direction: {choice.direction}")
	print(f"Model: {choice.path.name}")
	print("Required parameters: " + ", ".join(required_inputs))
	if known_outputs:
		print("Predicted outputs: " + ", ".join(known_outputs))

	provided_for_choice, invalid_for_choice = map_provided_to_required(required_inputs, provided)
	if invalid_for_choice:
		print(
			"\nSome provided parameters are not valid for "
			f"{pretty_label(choice.key)} ({choice.direction}) and were ignored: "
			+ ", ".join(invalid_for_choice)
		)
		print("Please provide parameters from: " + ", ".join(required_inputs))

	missing_initial = [p for p in required_inputs if p not in provided_for_choice]
	if missing_initial:
		print("\nRemaining parameters you can provide: " + ", ".join(missing_initial))
		print("If you skip them, dataset defaults will be used where available.")

	values, auto_filled = collect_missing_params(
		required_inputs,
		provided_for_choice,
		choice.key,
		data_cols,
	)

	while True:
		try:
			prediction = run_prediction(choice, required_inputs, values)
		except ValueError as exc:
			print(f"\n{exc}")
			print("Please provide the missing required values.")
			values, extra_auto = collect_missing_params(
				required_inputs,
				values,
				choice.key,
				data_cols,
				force_prompt=True,
				allow_autofill=False,
			)
			auto_filled.extend(p for p in extra_auto if p not in auto_filled)
			continue
		break

	print("\nInputs used for prediction:")
	for name in required_inputs:
		print(f"- {name}: {format_numeric_value(values[name])}")

	output_names = known_outputs
	if not output_names:
		output_names = infer_output_names_from_counterpart(choice, catalog, len(prediction))

	insensitive = model_looks_insensitive(choice, required_inputs, values, prediction)
	if insensitive:
		fallback = dataset_nearest_fallback_prediction(choice.key, required_inputs, output_names, values)
		if fallback is not None and len(fallback) == len(prediction):
			print(
				"\nWarning: Model appears insensitive for this topology in current environment. "
				"Using dataset-nearest fallback prediction instead."
			)
			prediction = fallback
		else:
			print(
				"\nWarning: This model produced the same output even after changing inputs. "
				"The artifact may be insensitive or version-incompatible."
			)

	print_results(output_names, prediction)

	if auto_filled:
		print(
			"\nNote: dataset defaults were used for: "
			+ ", ".join(sorted(set(auto_filled)))
		)


if __name__ == "__main__":
	main()
