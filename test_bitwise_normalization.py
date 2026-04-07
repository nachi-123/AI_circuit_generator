#!/usr/bin/env python3
"""Test script to verify digital value normalization."""

import ollama_trial as ot

# Test 1: Check circuit key detection
print("=" * 60)
print("TEST 1: Circuit Key Detection")
print("=" * 60)
ck = ot.normalize_key('and_gate')
print(f'Circuit key: "{ck}"')
print(f'In DIGITAL_CIRCUIT_HINTS: {ck in ot.DIGITAL_CIRCUIT_HINTS}')
domain = ot.classify_circuit_domain_from_key('and_gate')
print(f'Domain: {domain}')

# Test 2: Check normalization function
print("\n" + "=" * 60)
print("TEST 2: Normalization Function")
print("=" * 60)
inputs = {'A': 0.5, 'B': 0.5, 'supply_voltage_V': 5.0}
outputs = {'Y': 0.0}

print('Before normalization:')
print(f'  Inputs: {inputs}')
print(f'  Outputs: {outputs}')

norm_inputs, norm_outputs = ot.normalize_digital_values(inputs, outputs, 'and_gate')

print('\nAfter normalization:')
print(f'  Inputs: {norm_inputs}')
print(f'  Outputs: {norm_outputs}')

# Test 3: Check normalize_key on parameter names
print("\n" + "=" * 60)
print("TEST 3: Parameter Normalization")
print("=" * 60)
for key in ['A', 'B', 'Y', 'D0', 'Cin']:
    nk = ot.normalize_key(key)
    print(f'  {key} -> "{nk}"')

# Test 4: Check binary thresholds
print("\n" + "=" * 60)
print("TEST 4: Binary Threshold Tests")
print("=" * 60)
test_values = [0.0, 0.25, 0.5, 0.75, 1.0]
for val in test_values:
    binary = float(1 if val >= 0.5 else 0)
    print(f'  {val} -> {binary}')
