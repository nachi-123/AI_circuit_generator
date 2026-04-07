import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.multioutput import MultiOutputRegressor
import joblib

# ---------------- PATHS ---------------- #

DATA_PATH = "circuit_making\\visualizations\\inverting.py"

FWD_PATH = "models_forward/F_inverting_model.joblib"
BWD_PATH = "models_backward/B_inverting_model.joblib"

os.makedirs("models_forward", exist_ok=True)
os.makedirs("models_backward", exist_ok=True)

# ---------------- LOAD DATA ---------------- #

df = pd.read_csv(DATA_PATH)
df.columns = df.columns.str.strip()
df = df.dropna()

# ---------------- FEATURE ENGINEERING ---------------- #

# Key improvement
df["gain"] = df["Rf_ohm"] / df["Rin_ohm"]

# ---------------- FORWARD MODEL ---------------- #

def train_forward(df):

    print("Training FORWARD model...")

    X = df[["Vin_V", "gain"]]
    y = df["Vout_V"]

    scaler_X = StandardScaler()
    scaler_y = StandardScaler()

    X_scaled = scaler_X.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y.values.reshape(-1, 1)).ravel()

    model = MLPRegressor(
        hidden_layer_sizes=(128, 64),
        activation='relu',
        max_iter=2000,
        learning_rate_init=0.001
    )

    model.fit(X_scaled, y_scaled)

    joblib.dump((model, scaler_X, scaler_y), FWD_PATH)

    print("Saved forward model")


# ---------------- BACKWARD MODEL ---------------- #

def train_backward(df):

    print("Training BACKWARD model...")

    # Inputs → Vout + Vin
    X = df[["Vout_V", "Vin_V"]]

    # Outputs → gain only (better than predicting 2 values directly)
    y = df[["gain"]]

    scaler_X = StandardScaler()
    scaler_y = StandardScaler()

    X_scaled = scaler_X.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y)

    model = MLPRegressor(
        hidden_layer_sizes=(128, 64),
        activation='relu',
        max_iter=2000,
        learning_rate_init=0.001
    )

    model.fit(X_scaled, y_scaled)

    joblib.dump((model, scaler_X, scaler_y), BWD_PATH)

    print("Saved backward model")


# ---------------- PREDICTION HELPERS ---------------- #

def predict_forward(Vin, Rin, Rf):

    model, scaler_X, scaler_y = joblib.load(FWD_PATH)

    gain = Rf / Rin
    X = np.array([[Vin, gain]])

    X_scaled = scaler_X.transform(X)
    y_scaled = model.predict(X_scaled)

    Vout = scaler_y.inverse_transform(y_scaled.reshape(-1, 1))[0][0]

    return Vout


def predict_backward(Vin, Vout):

    model, scaler_X, scaler_y = joblib.load(BWD_PATH)

    X = np.array([[Vout, Vin]])
    X_scaled = scaler_X.transform(X)

    gain_scaled = model.predict(X_scaled)
    gain = scaler_y.inverse_transform(gain_scaled)[0][0]

    # Recover R values (choose base)
    Rin = 10000
    Rf = gain * Rin

    return Rin, Rf


# ---------------- MAIN ---------------- #

if __name__ == "__main__":

    train_forward(df)
    train_backward(df)

    print("\nTesting...")

    Vin = 5
    Rin = 10000
    Rf = 20000

    pred = predict_forward(Vin, Rin, Rf)
    print("Predicted Vout:", pred)

    Rin_pred, Rf_pred = predict_backward(Vin, pred)
    print("Recovered Rin, Rf:", Rin_pred, Rf_pred)