# apps/ml/registry.py
# PL: Prosty rejestr modeli/konfiguracji – zapis/odczyt artefaktów i metadanych.
# EN: Simple model/strategy registry – save/load artifacts & metadata.

from __future__ import annotations
import os, json, time, uuid
from typing import Dict, Any

REG_PATH = os.getenv("MODEL_REGISTRY_PATH", "/data/models")

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def save_artifact(kind: str, payload: Dict[str, Any]) -> str:
    """
    kind: e.g., 'strategy', 'booster', 'seq'
    Returns version_id string.
    """
    _ensure_dir(REG_PATH)
    ver = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    d = os.path.join(REG_PATH, f"{kind}-{ver}")
    _ensure_dir(d)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
    return ver

def load_artifact(kind: str, version: str) -> Dict[str, Any]:
    p = os.path.join(REG_PATH, f"{kind}-{version}", "meta.json")
    with open(p, "r") as f:
        return json.load(f)
