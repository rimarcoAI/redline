"""Player profile management with JSON persistence."""

import json
import os
from pathlib import Path

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"

DEFAULT_THRESHOLDS = {
    # Acceleration (horizontal g)
    "acc_threshold": 2.0,
    "acc_min_duration": 0.3,
    "acc_min_gap": 1.0,
    # Deceleration (derivative of horiz acc, g/s)
    "dec_threshold": 5.0,
    "dec_min_duration": 0.2,
    "dec_min_gap": 1.0,
    # Jumps (az in g)
    "jump_threshold": 2.5,
    "jump_min_duration": 0.15,
    "jump_min_gap": 0.8,
    # Direction changes (gyro magnitude, deg/s)
    "dir_threshold": 150.0,
    "dir_min_duration": 0.15,
    "dir_min_gap": 0.5,
    # High load (instantaneous player load)
    "load_threshold": 0.05,
    "load_min_duration": 0.2,
    "load_min_gap": 0.5,
}


class ProfileManager:
    def __init__(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(
            p.stem for p in PROFILES_DIR.glob("*.json")
        )

    def load(self, name: str) -> dict:
        path = PROFILES_DIR / f"{name}.json"
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, name: str, data: dict) -> None:
        path = PROFILES_DIR / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def delete(self, name: str) -> bool:
        path = PROFILES_DIR / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def get_thresholds(self, name: str) -> dict:
        profile = self.load(name)
        thresholds = DEFAULT_THRESHOLDS.copy()
        thresholds.update(profile.get("thresholds", {}))
        return thresholds

    def save_thresholds(self, name: str, thresholds: dict) -> None:
        profile = self.load(name)
        profile["thresholds"] = thresholds
        self.save(name, profile)

    def create_profile(self, name: str, info: dict) -> None:
        profile = {
            "nombre": name,
            "info": info,
            "thresholds": DEFAULT_THRESHOLDS.copy(),
        }
        self.save(name, profile)

    def get_info(self, name: str) -> dict:
        return self.load(name).get("info", {})
