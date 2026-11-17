import pytest
from src.persistence.engine.redis.geometric_guards import (
    clamp_distance_result,
    is_distance_valid,
)


@pytest.mark.parametrize(
    "raw_distance, expected_valid",
    [
        (float("nan"), False),
        (float("inf"), False),
        (float("-inf"), False),
        (0.0, True),
        (1.5, True),
        (-0.0005, True),
    ],
)
def test_is_distance_valid_traps_ieee754_anomalies(
    raw_distance: float, expected_valid: bool
):
    """Check IEEE 754 NaN or Inf values are rejected."""
    assert (
        is_distance_valid(raw_distance=raw_distance, doc_id="test_doc_id")
        is expected_valid
    )


@pytest.mark.parametrize(
    "raw_distance, metric, expected_similarity",
    [
        # =================================================================
        # COSINE / IP [-0.001, 2.001], Clamping: [0.0, 2.0]
        # =================================================================
        # Nominal cases COSINE
        (0.0, "COSINE", 1.0),  # 1.0 - (0.0 / 2.0) = 1.0 = 100%
        (1.0, "cosine", 0.5),  # 1.0 - (1.0 / 2.0) = 0.5 = 50%
        (2.0, "CoSiNe", 0.0),  # 1.0 - (2.0 / 2.0) = 0.0 = 0%
        # Nominal cases IP
        (0.0, "IP", 1.0),  # 1.0 - (0.0 / 2.0) = 1.0 = 100%
        (1.0, "Ip", 0.5),  # 1.0 - (1.0 / 2.0) = 0.5 = 50%
        (2.0, "iP", 0.0),  # 1.0 - (2.0 / 2.0) = 0.0 = 0%
        # Micro-overlaps COSINE, 2.0003 to 2.0, -0.0005 to 0.0
        (2.0003, "COSINE", 0.0),  # 1.0 - (2.0 / 2.0) = 0.0 = 0%
        (-0.0005, "COSINE", 1.0),  # 1.0 - (0.0 / 2.0) = 1.0 = 100%
        # Micro-overlaps IP, 2.0003 to 2.0, -0.0005 to 0.0
        (2.0003, "IP", 0.0),  # 1.0 - (2.0 / 2.0) = 0.0 = 0%
        (-0.0005, "IP", 1.0),  # 1.0 - (0.0 / 2.0) = 1.0 = 100%
        # COSINE Aberrations should be evicted
        (2.0015, "COSINE", None),  # 2.0015 > 2.001, then result is None
        (-0.0015, "COSINE", None),  # -0.0015 < -0.001, then result is None
        # IP Aberrations should be evicted
        (2.0015, "IP", None),  # 2.0015 > 2.001, then result is None
        (-0.0015, "IP", None),  # -0.0015 < -0.001, then result is None
        # =================================================================
        # L2 [-0.001, ...], Clamping: [0.0, ...]
        # =================================================================
        # Nominal cases
        (0.0, "L2", 1.0),  # 1.0 / (1.0 + 0.0) = 1.0 = 100%
        (1.0, "L2", 0.5),  # 1.0 / (1.0 + 1.0) = 0.5 = 50%
        (3.0, "l2", 0.25),  # 1.0 / (1.0 + 3.0) = 0.25 = 25%
        # Micro-overlaps L2, -0.0003 to 0.0
        (-0.0003, "L2", 1.0),  # 1.0 / (1.0 + 0.0) = 1.0 = 100%
        # L2 Aberrations should be evicted
        (-0.0015, "L2", None),  # -0.0015 < -0.001, then result is None
    ],
)
def test_clamp_distance_result_applies_correct_boundaries(
    raw_distance: float, metric: str, expected_similarity: float | None
):
    """Check clamping and eviction"""
    similarity = clamp_distance_result(
        raw_distance=raw_distance, doc_id="test_doc_id", metric=metric
    )

    if expected_similarity is None:
        assert similarity is None
    else:
        assert similarity == expected_similarity


@pytest.mark.parametrize("unsupported_metric", ["unknown", ""])
def test_clamp_distance_result_raises_on_unsupported_metric(unsupported_metric: str):
    """Ensure unsupported vector distance metrics fail fast with a RuntimeError."""
    with pytest.raises(
        RuntimeError,
        match=f"Unsupported database structural index metric: {unsupported_metric}",
    ):
        clamp_distance_result(
            raw_distance=0.5,
            doc_id="test_doc_id",
            metric=unsupported_metric,
        )
