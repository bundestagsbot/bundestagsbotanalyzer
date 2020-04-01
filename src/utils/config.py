import os.path
import json

from .console import Console, red, white

BASE_PATH = content_dir = "config" if os.path.isdir("config") else "config-default"

PATHS = ["main.json"]
SHL = Console("ConfigLoader", cls=True)


class Config:
    def __init__(self):
        self.options = {}
        self.reload()

    def reload(self, debug=False):
        SHL.output(f"Reloading config.")
        files_failed = 0
        for path in PATHS:
            SHL.output(f"Reloading configfile {os.path.join(BASE_PATH, path)}")
            with open(os.path.join(BASE_PATH, path), 'r', encoding="utf-8") as c:
                data = json.load(c)
            if data is None:
                files_failed += 1
                continue
            for key, value in data.items():
                self.options[key] = value
                if debug:
                    SHL.output(f"[{key}]: {value}")
        SHL.output(f"{red}========================{white}")
        return files_failed

    def get(self, key: str, default=None):
        return self.options.get(key, default)


cfg = Config()
