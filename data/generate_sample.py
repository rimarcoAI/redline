"""Generate synthetic basketball IMU session data for testing."""

import numpy as np
import pandas as pd
from pathlib import Path


def generate_session(duration_minutes: float = 5.0, fs: int = 100, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = int(duration_minutes * 60 * fs)
    t = np.arange(n) / fs

    # Base sensor noise
    ax = rng.normal(0, 0.08, n)
    ay = rng.normal(0, 0.08, n)
    az = np.full(n, 1.0) + rng.normal(0, 0.04, n)  # gravity baseline
    gx = rng.normal(0, 0.3, n)
    gy = rng.normal(0, 0.3, n)
    gz = rng.normal(0, 0.3, n)

    # Continuous running pattern (jogging stride at ~2.5 Hz)
    stride_freq = 2.5
    ax += 0.25 * np.sin(2 * np.pi * stride_freq * t + rng.uniform(0, np.pi))
    ay += 0.15 * np.sin(2 * np.pi * stride_freq * t + rng.uniform(0, np.pi))
    az += 0.18 * np.sin(2 * np.pi * stride_freq * 2 * t)

    def add_burst(arr, time_s, dur_s, peak, shape="ramp-hold"):
        s = int(time_s * fs)
        d = int(dur_s * fs)
        if s + d >= n:
            return
        if shape == "ramp-hold":
            ramp = int(d * 0.35)
            profile = np.concatenate(
                [np.linspace(0, peak, ramp), np.full(d - ramp, peak)]
            )
        elif shape == "pulse":
            profile = peak * np.sin(np.linspace(0, np.pi, d))
        elif shape == "spike":
            half = d // 2
            profile = np.concatenate([np.linspace(0, peak, half), np.linspace(peak, 0, d - half)])
        else:
            profile = np.full(d, peak)
        arr[s: s + d] += profile + rng.normal(0, abs(peak) * 0.07, d)

    # --- Acceleration events (sprints) ---
    sprint_times = [8, 40, 85, 130, 175, 220, 260]
    for st in sprint_times:
        dur = rng.uniform(1.8, 4.5)
        peak = rng.uniform(2.2, 4.0)
        add_burst(ax, st, dur, peak, "ramp-hold")
        add_burst(ay, st, dur, peak * 0.3, "ramp-hold")

    # --- Deceleration events ---
    decel_times = [20, 55, 105, 158, 200, 245, 278]
    for dt in decel_times:
        dur = rng.uniform(0.8, 2.0)
        peak = rng.uniform(2.5, 5.5)
        add_burst(ax, dt, dur, -peak, "spike")

    # --- Jump events (high az spike then landing) ---
    jump_times = [18, 48, 95, 143, 188, 235, 270]
    for jt in jump_times:
        launch_dur = 0.12
        air_dur = rng.uniform(0.3, 0.55)
        land_dur = 0.18

        # Launch (upward thrust)
        add_burst(az, jt, launch_dur, rng.uniform(2.5, 4.5), "pulse")
        # Air time (near-zero vertical acceleration ~free fall)
        s_air = int((jt + launch_dur) * fs)
        d_air = int(air_dur * fs)
        if s_air + d_air < n:
            az[s_air: s_air + d_air] -= 0.9  # reduced gravity in air
        # Landing impact
        add_burst(az, jt + launch_dur + air_dur, land_dur, rng.uniform(4.0, 7.0), "pulse")
        # Some lateral on landing
        add_burst(ax, jt + launch_dur + air_dur, 0.1, rng.uniform(0.5, 1.5), "pulse")

    # --- Direction changes (high gyroscope spikes) ---
    dir_times = [15, 38, 72, 120, 165, 210, 255]
    for dct in dir_times:
        dur = rng.uniform(0.3, 1.2)
        peak_gz = rng.uniform(160, 400)
        add_burst(gz, dct, dur, peak_gz, "pulse")
        add_burst(gx, dct, dur, peak_gz * 0.4, "pulse")
        add_burst(ax, dct, dur * 0.5, rng.uniform(1.0, 2.5), "pulse")

    # --- Rest periods ---
    rest_times = [(70, 78), (150, 160), (240, 252)]
    for rs, re in rest_times:
        si, ei = int(rs * fs), int(re * fs)
        if ei < n:
            ax[si:ei] *= 0.05
            ay[si:ei] *= 0.05
            az[si:ei] = 1.0 + rng.normal(0, 0.02, ei - si)
            gx[si:ei] *= 0.05
            gy[si:ei] *= 0.05
            gz[si:ei] *= 0.05

    # Compute Euler angles by simple gyro integration (representative, not precise)
    roll = np.cumsum(gx / fs)
    pitch = np.cumsum(gy / fs)
    yaw = np.cumsum(gz / fs)
    roll = ((roll + 180) % 360) - 180
    pitch = ((pitch + 90) % 180) - 90
    yaw = ((yaw + 180) % 360) - 180

    timestamps = pd.date_range("2024-01-15 10:00:00", periods=n, freq=f"{1000 // fs}ms")

    return pd.DataFrame(
        {
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "ax": ax.round(4),
            "ay": ay.round(4),
            "az": az.round(4),
            "gx": gx.round(4),
            "gy": gy.round(4),
            "gz": gz.round(4),
            "roll": roll.round(4),
            "pitch": pitch.round(4),
            "yaw": yaw.round(4),
        }
    )


if __name__ == "__main__":
    out = Path(__file__).parent / "sample_session.csv"
    df = generate_session(duration_minutes=5, fs=100)
    df.to_csv(out, index=False)
    print(f"Datos de ejemplo generados: {out}  ({len(df)} muestras)")
