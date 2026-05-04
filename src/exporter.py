"""Export detected events and session data to CSV."""

import io
import pandas as pd


def events_to_dataframe(events: dict) -> pd.DataFrame:
    """Flatten all event categories into a single DataFrame."""
    all_records = []
    for category, records in events.items():
        all_records.extend(records)

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    export_cols = [
        "tipo", "inicio", "fin", "inicio_s", "fin_s",
        "duracion_s", "pico", "media",
    ]
    df = df[[c for c in export_cols if c in df.columns]]
    df = df.sort_values("inicio_s").reset_index(drop=True)
    return df


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8")
    return buffer.getvalue()


def session_summary_to_csv_bytes(summary: dict) -> bytes:
    df = pd.DataFrame(list(summary.items()), columns=["Métrica", "Valor"])
    return to_csv_bytes(df)
