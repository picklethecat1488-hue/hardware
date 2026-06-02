"""Utility functions for method caching and coordinate data parsing."""

from functools import wraps
import inspect
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, TypeVar, overload, cast
import numpy as np
import yaml

T = TypeVar("T", bound=Callable[..., Any])


def _make_hashable(obj: Any) -> Any:
    """Recursively convert unhashable types into hashable ones."""
    if isinstance(obj, (list, tuple)):
        return tuple(_make_hashable(i) for i in obj)
    if isinstance(obj, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in obj.items()))
    return obj


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
            key = (_make_hashable(args), _make_hashable(kwargs))
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


def load_measurements(path: str) -> dict[int | str, np.ndarray]:
    """
    Load and parse the measurements YAML file and return processed numpy arrays.

    Example YAML (list format):
    ```yaml
    - [0, 0, 0]
    - [1, 2, 3]
    ```
    Returns: {1: array([0, 0, 0]), 2: array([1, 2, 3])}

    Example YAML (dict format):
    ```yaml
    p1: [0, 0, 0]
    p2: [1, 2, 3]
    ```
    Returns: {'p1': array([0, 0, 0]), 'p2': array([1, 2, 3])}

    Example YAML (nested section):
    ```yaml
    section_a:
      p1: [0, 0, 0]
      p2: [1, 2, 3]
    section_b:
      p3: [4, 5, 6]
    ```
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}

    with open(file_path, "r") as f:
        try:
            data = yaml.safe_load(f) or {}
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
