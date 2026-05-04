"""Signal processing for IMU sensor data."""

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt


REQUIRED_COLUMNS = {"timestamp", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch", "yaw"}


def load_csv(file) -> tuple[pd.DataFrame, str | None]:
    """Load and validate CSV. Returns (df, error_message)."""
    try:
        df = pd.read_csv(file)
    except Exception as e:
        return None, f"Error al leer el archivo: {e}"

    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return None, f"Columnas faltantes: {', '.join(sorted(missing))}"

    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    except Exception:
        return None, "La columna 'timestamp' no tiene formato de fecha/hora válido."

    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch", "yaw"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[list(REQUIRED_COLUMNS - {"timestamp"})].isnull().any().any():
        return None, "Hay valores no numéricos en las columnas de señal."

    return df, None


def estimate_fs(df: pd.DataFrame) -> float:
    """Estimate sampling frequency in Hz from timestamps."""
    if len(df) < 2:
        return 100.0
    dt = df["timestamp"].diff().dropna().dt.total_seconds()
    median_dt = dt.median()
    if median_dt <= 0:
        return 100.0
    return round(1.0 / median_dt)


def _lowpass(signal: np.ndarray, cutoff: float, fs: float, order: int = 4) -> np.ndarray:
    nyq = fs / 2
    if cutoff >= nyq:
        return signal
    b, a = butter(order, cutoff / nyq, btype="low")
    return filtfilt(b, a, signal)


def compute_metrics(df: pd.DataFrame, fs: float) -> pd.DataFrame:
    """Add derived metric columns to df."""
    df = df.copy()

    # Horizontal acceleration magnitude (removes gravity component in z)
    df["acc_horiz"] = np.sqrt(df["ax"] ** 2 + df["ay"] ** 2)

    # Total acceleration magnitude
    df["acc_mag"] = np.sqrt(df["ax"] ** 2 + df["ay"] ** 2 + df["az"] ** 2)

    # Gyroscope magnitude (deg/s)
    df["gyro_mag"] = np.sqrt(df["gx"] ** 2 + df["gy"] ** 2 + df["gz"] ** 2)

    # Smooth horizontal acceleration for deceleration detection
    df["acc_horiz_smooth"] = _lowpass(df["acc_horiz"].values, cutoff=5.0, fs=fs)

    # Instantaneous acceleration derivative (for deceleration)
    df["acc_deriv"] = np.gradient(df["acc_horiz_smooth"].values, 1.0 / fs)

    # Vertical acceleration (subtract gravity offset, assume z-axis up)
    az_centered = df["az"].values - np.median(df["az"].values)
    df["az_centered"] = az_centered

    # Smooth az for jump detection
    df["az_smooth"] = _lowpass(df["az"].values, cutoff=10.0, fs=fs)

    # Player Load (instantaneous: sqrt(sum of squared delta per axis) / fs)
    d_ax = np.gradient(df["ax"].values, 1.0 / fs)
    d_ay = np.gradient(df["ay"].values, 1.0 / fs)
    d_az = np.gradient(df["az"].values, 1.0 / fs)
    df["load_instant"] = np.sqrt(d_ax**2 + d_ay**2 + d_az**2) / fs

    # Cumulative player load
    df["load_cumul"] = df["load_instant"].cumsum()

    # Time in seconds from start
    t0 = df["timestamp"].iloc[0]
    df["time_s"] = (df["timestamp"] - t0).dt.total_seconds()

    return df


def compute_session_summary(df: pd.DataFrame, events: dict, fs: float) -> dict:
    """Compute high-level session statistics."""
    duration_s = df["time_s"].iloc[-1]
    total_load = df["load_cumul"].iloc[-1]
    load_per_min = total_load / (duration_s / 60) if duration_s > 0 else 0

    n_acc = len(events.get("accelerations", []))
    n_dec = len(events.get("decelerations", []))
    n_jmp = len(events.get("jumps", []))
    n_dir = len(events.get("direction_changes", []))

    peak_acc = df["acc_horiz"].max()
    peak_gyro = df["gyro_mag"].max()

    # Estimate active vs rest time using load threshold
    load_threshold = df["load_instant"].quantile(0.3)
    active_ratio = (df["load_instant"] > load_threshold).mean()

    return {
        "Duración (s)": round(duration_s, 1),
        "Duración (min)": round(duration_s / 60, 2),
        "Frecuencia muestral (Hz)": fs,
        "Total muestras": len(df),
        "Player Load total": round(total_load, 2),
        "Player Load / min": round(load_per_min, 2),
        "Aceleraciones detectadas": n_acc,
        "Deceleraciones detectadas": n_dec,
        "Saltos detectados": n_jmp,
        "Cambios de dirección detectados": n_dir,
        "Total eventos": n_acc + n_dec + n_jmp + n_dir,
        "Aceleración horiz. máx. (g)": round(peak_acc, 3),
        "Giroscopio máx. (°/s)": round(peak_gyro, 1),
        "Ratio activo (%)": round(active_ratio * 100, 1),
    }
