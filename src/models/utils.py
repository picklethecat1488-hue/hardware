"""Utility functions for method caching and coordinate data parsing."""

from functools import wraps
import inspect
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, TypeVar, overload, cast
import numpy as np
import yaml

T = TypeVar("T", bound=Callable[..., Any])


@overload
def method_cache(func: Callable[..., Any]) -> Callable[..., Any]: ...


@overload
def method_cache(*, maxsize: int = 128) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def method_cache(func: Callable[..., Any] | None = None, *, maxsize: int = 128) -> Any:
    """Create per-instance cache to avoid memory leaks and Pydantic @validate_call conflicts."""

    def decorator(f: T) -> T:
        @wraps(f)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            cache_attr = f"_cache_{f.__name__}"
            if not hasattr(self, cache_attr):
                setattr(self, cache_attr, OrderedDict())
            cache = getattr(self, cache_attr)
            key = (args, tuple(sorted(kwargs.items())))
            if key in cache:
                cache.move_to_end(key)
                return cache[key]
            result = f(self, *args, **kwargs)
            cache[key] = result
            if len(cache) > maxsize:
                cache.popitem(last=False)
            return result

        try:
            setattr(wrapper, "__signature__", inspect.signature(f))
        except (ValueError, TypeError):
            pass

        if hasattr(wrapper, "__wrapped__"):
            delattr(wrapper, "__wrapped__")

        return cast(T, wrapper)

    if func is None:
        return decorator
    return decorator(func)


def parse_measurements(path: str) -> dict[int | str, np.ndarray]:
    """Parse the measurements YAML file and return processed numpy arrays."""
    if ":" in path:
        file_path_str, key = path.split(":", 1)
    else:
        file_path_str, key = path, None

    file_path = Path(file_path_str)
    if not file_path.exists():
        return {}

    with open(file_path, "r") as f:
        try:
            raw_data = yaml.safe_load(f) or {}
            data = raw_data.get(key, {}) if key else raw_data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML at {file_path}") from e

    p = {}
    if isinstance(data, list):
        for idx, item in enumerate(data):
            p[idx + 1] = np.array(item, dtype=float)
    elif isinstance(data, dict):
        for k, item in data.items():
            p[k] = np.array(item, dtype=float)
    return p
