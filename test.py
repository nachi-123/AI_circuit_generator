import pandas as pd

clean_rows = []

with open("datasets\ANALOG\inverting.csv", "r") as f:
    for line in f:

        line = line.strip()

        if not line:
            continue

        # Try different separators
        if "," in line:
            parts = line.split(",")
        elif ";" in line:
            parts = line.split(";")
        else:
            parts = line.split()

        # Keep only rows with 4 values
        if len(parts) == 4:
            clean_rows.append(parts)

# 🚨 SAFETY CHECK
if len(clean_rows) == 0:
    raise ValueError("No valid rows found in CSV. File is corrupted.")

# Create DataFrame
df = pd.DataFrame(clean_rows[1:], columns=clean_rows[0])

df.to_csv("data/inverting_clean.csv", index=False)

print("Cleaned file saved successfully!")