import os
import json
from argparse import Namespace

CONFIG_DIR = os.path.expanduser("~/.config/song-dl")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "format": "mp3",
    "quality": "0",
    "skip_existing": False,
    "no_cover": False,
    "no_metadata": False,
    "output_pattern": "{artist} - {title}",
    "sources": ["ytsearch", "scsearch"],
    "max_results": 5,
    "debug": False,
}


def load():
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    cfg = Namespace()
    for k, v in DEFAULTS.items():
        setattr(cfg, k, data.get(k, v))

    if not isinstance(cfg.max_results, int) or not (1 <= cfg.max_results <= 20):
        cfg.max_results = DEFAULTS["max_results"]

    BOOL_FIELDS = ("skip_existing", "no_cover", "no_metadata", "debug")
    for k in BOOL_FIELDS:
        if not isinstance(getattr(cfg, k), bool):
            setattr(cfg, k, DEFAULTS[k])

    return cfg


def save(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = {k: getattr(cfg, k, v) for k, v in DEFAULTS.items()}
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)
