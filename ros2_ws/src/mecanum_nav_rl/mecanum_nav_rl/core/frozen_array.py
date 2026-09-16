"""Utilities for creating safe read-only float32 NumPy arrays."""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray


FrozenFloat32Array: TypeAlias = NDArray[np.float32]

_ALLOWED_SOURCE_DTYPE_KINDS = frozenset({"i", "u", "f"})


def freeze_float32_array(
    values: object,
    *,
    name: str = "array",
    expected_ndim: int | None = None,
) -> FrozenFloat32Array:
    """Create an independent, finite, read-only float32 NumPy array.

    Only integer and real floating-point input values are accepted. The
    returned array is a copy, so later changes to the input cannot change it.
    """

    if expected_ndim is not None:
        if isinstance(expected_ndim, bool) or not isinstance(expected_ndim, int):
            raise TypeError("expected_ndim must be an integer or None")

        if expected_ndim < 0:
            raise ValueError("expected_ndim must be non-negative")

    try:
        source_array = np.asarray(values)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{name} cannot be converted to a NumPy array"
        ) from error

    if source_array.dtype.kind not in _ALLOWED_SOURCE_DTYPE_KINDS:
        raise TypeError(
            f"{name} must contain real numeric values, not "
            f"dtype '{source_array.dtype}'"
        )

    try:
        array = np.asarray(source_array, dtype=np.float32)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            f"{name} cannot be converted to a float32 NumPy array"
        ) from error

    if expected_ndim is not None and array.ndim != expected_ndim:
        raise ValueError(
            f"{name} must have {expected_ndim} dimensions, "
            f"but has {array.ndim}"
        )

    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must not contain NaN or infinity")

    frozen_array = np.array(
        array,
        dtype=np.float32,
        copy=True,
        order="C",
    )
    frozen_array.setflags(write=False)

    return frozen_array
