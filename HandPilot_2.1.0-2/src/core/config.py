from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class ConfigStore:
    """Thread-safe JSON config with default migration for older user configs."""

    def __init__(self, path: str | Path, default_path: str | Path):
        self.path = Path(path)
        self.default_path = Path(default_path)
        self._lock = RLock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        with self.default_path.open("r", encoding="utf-8") as handle:
            defaults = json.load(handle)
        if not self.path.exists():
            return defaults
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                user = json.load(handle)
        except (OSError, json.JSONDecodeError):
            # A damaged user config should never prevent the app from starting.
            return defaults
        if not isinstance(user, dict):
            return defaults
        return _deep_merge(defaults, user)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def replace(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._data = deepcopy(data)
            self.save()

    def update_path(self, path: str, value: Any, save: bool = True) -> None:
        with self._lock:
            node: dict[str, Any] = self._data
            parts = path.split(".")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
            if save:
                self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2)
        temp.replace(self.path)

    def get(self, path: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for part in path.split("."):
                if not isinstance(node, dict) or part not in node:
                    return deepcopy(default)
                node = node[part]
            return deepcopy(node)
