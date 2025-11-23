import os
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ["true", "1", "yes"]


def env_none_or_str(name: str, default=None):
    value = os.getenv(name)
    if value is None or value.lower() == "none":
        return default
    return value
