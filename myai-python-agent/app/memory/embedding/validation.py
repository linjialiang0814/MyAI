from __future__ import annotations

import numpy as np


def validate_embedding_vector(vector, expected_dimensions: int = 0) -> np.ndarray:
    """Return a finite one-dimensional float32 vector or raise a safe error."""

    result = np.asarray(vector, dtype=np.float32)
    if result.ndim != 1:
        raise ValueError("Embedding response must be a one-dimensional vector")
    if result.size == 0:
        raise ValueError("Embedding response cannot be empty")
    if not np.isfinite(result).all():
        raise ValueError("Embedding response contains non-finite values")
    if expected_dimensions > 0 and result.size != expected_dimensions:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dimensions}, got {result.size}"
        )
    return result
