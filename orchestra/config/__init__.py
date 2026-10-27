"""
Config-Loader: lädt settings.yaml in ein dict, mit Defaults als Fallback.
Kein yaml-Paket nötig falls nicht installiert -> einfacher JSON/YAML-Parser.
"""
from pathlib import Path
import json

from orchestra.config import paths

# Minimaler YAML-Parser (nur einfache Strukturen, kein Voll-YAML nötig)
def _parse_yaml(text: str) -> dict:
    result = {}
    stack = [result]
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        depth = indent // 2
        while len(stack) > depth + 1:
            stack.pop()
        key, _, val = line.strip().partition(":")
        key = key.strip()
        val = val.strip()
        if val and not val.startswith("#"):
            val = val.split("#")[0].strip()
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            elif val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            else:
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        val = val.strip("'\"")
        else:
            val = {}
        node = stack[depth]
        node[key] = val
        if isinstance(val, dict):
            stack.append(val)
    return result


_CONFIG = None

def load_config() -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    f = paths.ORCHESTRA_ROOT / "config" / "settings.yaml"
    if f.exists():
        _CONFIG = _parse_yaml(f.read_text())
    else:
        _CONFIG = {}
    return _CONFIG


def get(key: str, default=None):
    """Verschachtelten Key lesen, z.B. get('conductor.buy_threshold', 0.5)."""
    cfg = load_config()
    node = cfg
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


if __name__ == "__main__":
    cfg = load_config()
    print("Symbols:", cfg.get("universe", {}).get("symbols"))
    print("Buy threshold:", get("conductor.buy_threshold"))
    print("Quant features:", get("agents.quant.features"))
