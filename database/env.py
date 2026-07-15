from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


def load_local_env(env_path: str | Path = ".env") -> None:
    """Load local .env without overriding real environment variables.

    Uses python-dotenv when it is installed. Missing .env is normal for packaged
    installs and should not crash the application.
    """
    path = Path(env_path)
    if not path.exists():
        return
    if importlib.util.find_spec("dotenv") is None:
        return
    dotenv = importlib.import_module("dotenv")
    dotenv.load_dotenv(path, override=False)
