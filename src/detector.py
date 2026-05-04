"""Grouped event detection for IMU basketball data."""

import numpy as np
import pandas as pd


def _find_groups(mask: np.ndarray, min_samples: int, min_gap_samples: int) -> list[tuple[int, int]]:
    """
    Convert a boolean mask into grouped (start, end) index pairs.
    Merges events separated by less than min_gap_samples and filters
    events shorter than min_samples. This gives one event record per
    physical action, not one per sample.
    """
    padded = np.concatenate([[False], mask.astype(bool), [False]])
    diff = np.diff(padded.astype(np.int8))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]

    if len(starts) == 0:
        return []

    # Merge events that are too close
    merged_starts = [starts[0]]
    merged_ends = [ends[0]]
    for i in range(1, len(starts)):
        if starts[i] - merged_ends[-1] < min_gap_samples:
            merged_ends[-1] = ends[i]
        else:
            merged_starts.append(starts[i])
            merged_ends.append(ends[i])

    return [(s, e) for s, e in zip(merged_starts, merged_ends) if e - s >= min_samples]


def _groups_to_records(
    df: pd.DataFrame,
    groups: list[tuple[int, int]],
    signal_col: str,
    event_type: str,
) -> list[dict]:
    """Convert index pairs into event records with metadata."""
    records = []
    for s, e in groups:
        seg = df.iloc[s:e]
        records.append(
            {
                "tipo": event_type,
                "inicio": df["timestamp"].iloc[s],
                "fin": df["timestamp"].iloc[e - 1],
                "inicio_s": round(df["time_s"].iloc[s], 3),
                "fin_s": round(df["time_s"].iloc[e - 1], 3),
                "duracion_s": round(df["time_s"].iloc[e - 1] - df["time_s"].iloc[s], 3),
                "pico": round(float(seg[signal_col].max()), 4),
                "media": round(float(seg[signal_col].mean()), 4),
                "idx_inicio": s,
                "idx_fin": e,
            }
        )
    return records


def detect_accelerations(
    df: pd.DataFrame,
    threshold: float,
    min_duration_s: float,
    min_gap_s: float,
    fs: float,
) -> list[dict]:
    """Detect horizontal acceleration bursts (sprints)."""
    min_samples = max(1, int(min_duration_s * fs))
    min_gap_samples = max(1, int(min_gap_s * fs))
    mask = df["acc_horiz"].values > threshold
    groups = _find_groups(mask, min_samples, min_gap_samples)
    return _groups_to_records(df, groups, "acc_horiz", "Aceleración")


def detect_decelerations(
    df: pd.DataFrame,
    threshold: float,
    min_duration_s: float,
    min_gap_s: float,
    fs: float,
) -> list[dict]:
    """Detect deceleration events (negative derivative of smooth horiz. acc)."""
    min_samples = max(1, int(min_duration_s * fs))
    min_gap_samples = max(1, int(min_gap_s * fs))
    # Deceleration = negative horiz acceleration derivative beyond threshold
    mask = df["acc_deriv"].values < -abs(threshold)
    groups = _find_groups(mask, min_samples, min_gap_samples)
    # For decelerations, peak is the most negative derivative value
    records = []
    for s, e in groups:
        seg = df.iloc[s:e]
        records.append(
            {
                "tipo": "Deceleración",
                "inicio": df["timestamp"].iloc[s],
                "fin": df["timestamp"].iloc[e - 1],
                "inicio_s": round(df["time_s"].iloc[s], 3),
                "fin_s": round(df["time_s"].iloc[e - 1], 3),
                "duracion_s": round(df["time_s"].iloc[e - 1] - df["time_s"].iloc[s], 3),
                "pico": round(float(seg["acc_deriv"].min()), 4),
                "media": round(float(seg["acc_deriv"].mean()), 4),
                "idx_inicio": s,
                "idx_fin": e,
            }
        )
    return records


def detect_jumps(
    df: pd.DataFrame,
    threshold: float,
    min_duration_s: float,
    min_gap_s: float,
    fs: float,
) -> list[dict]:
    """Detect jump events via vertical (az) acceleration peaks."""
    min_samples = max(1, int(min_duration_s * fs))
    min_gap_samples = max(1, int(min_gap_s * fs))
    mask = df["az_smooth"].values > threshold
    groups = _find_groups(mask, min_samples, min_gap_samples)
    return _groups_to_records(df, groups, "az_smooth", "Salto")


def detect_direction_changes(
    df: pd.DataFrame,
    threshold: float,
    min_duration_s: float,
    min_gap_s: float,
    fs: float,
) -> list[dict]:
    """Detect direction changes via gyroscope magnitude spikes."""
    min_samples = max(1, int(min_duration_s * fs))
    min_gap_samples = max(1, int(min_gap_s * fs))
    mask = df["gyro_mag"].values > threshold
    groups = _find_groups(mask, min_samples, min_gap_samples)
    return _groups_to_records(df, groups, "gyro_mag", "Cambio de dirección")


def detect_high_load(
    df: pd.DataFrame,
    threshold: float,
    min_duration_s: float,
    min_gap_s: float,
    fs: float,
) -> list[dict]:
    """Detect periods of high instantaneous load."""
    min_samples = max(1, int(min_duration_s * fs))
    min_gap_samples = max(1, int(min_gap_s * fs))
    mask = df["load_instant"].values > threshold
    groups = _find_groups(mask, min_samples, min_gap_samples)
    return _groups_to_records(df, groups, "load_instant", "Alta carga")


def detect_all_events(df: pd.DataFrame, thresholds: dict, fs: float) -> dict:
    """Run all detectors and return categorized event lists."""
    t = thresholds
    return {
        "accelerations": detect_accelerations(
            df,
            threshold=t["acc_threshold"],
            min_duration_s=t["acc_min_duration"],
            min_gap_s=t["acc_min_gap"],
            fs=fs,
        ),
        "decelerations": detect_decelerations(
            df,
            threshold=t["dec_threshold"],
            min_duration_s=t["dec_min_duration"],
            min_gap_s=t["dec_min_gap"],
            fs=fs,
        ),
        "jumps": detect_jumps(
            df,
            threshold=t["jump_threshold"],
            min_duration_s=t["jump_min_duration"],
            min_gap_s=t["jump_min_gap"],
            fs=fs,
        ),
        "direction_changes": detect_direction_changes(
            df,
            threshold=t["dir_threshold"],
            min_duration_s=t["dir_min_duration"],
            min_gap_s=t["dir_min_gap"],
            fs=fs,
        ),
        "high_load": detect_high_load(
            df,
            threshold=t["load_threshold"],
            min_duration_s=t["load_min_duration"],
            min_gap_s=t["load_min_gap"],
            fs=fs,
        ),
    }
