from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_COLORS = {
    "background": "black",
    "foreground": "white",
    "muted": "bright_black",
    "border": "cyan",
    "title": "bright_cyan",
    "accent": "magenta",
    "ok": "green",
    "warn": "yellow",
    "bad": "red",
    "bar_low": "blue",
    "bar_mid": "cyan",
    "bar_high": "green",
    "used": "bright_green",
}

DEFAULT_SYMBOLS = {
    "fix": "FIX",
    "satellite": "SAT",
    "accuracy": "ACC",
    "speed": "SPD",
    "altitude": "ALT",
    "time": "UTC",
}


@dataclass(frozen=True)
class Theme:
    colors: dict[str, str]
    symbols: dict[str, str]

    def color(self, name: str) -> str:
        return self.colors.get(name, DEFAULT_COLORS.get(name, "white"))

    def symbol(self, name: str) -> str:
        return self.symbols.get(name, DEFAULT_SYMBOLS.get(name, ""))


def load_theme(path: Path | None) -> Theme:
    colors = dict(DEFAULT_COLORS)
    symbols = dict(DEFAULT_SYMBOLS)

    if path is None or not path.exists():
        return Theme(colors=colors, symbols=symbols)

    data = _load_toml(path)
    colors.update(_string_map(data.get("colors", {})))
    symbols.update(_string_map(data.get("symbols", {})))
    return Theme(colors=colors, symbols=symbols)


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return {}

    with path.open("rb") as file:
        loaded = tomllib.load(file)
    return loaded if isinstance(loaded, dict) else {}


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
