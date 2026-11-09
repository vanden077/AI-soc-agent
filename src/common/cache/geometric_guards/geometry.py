import logging
import math

logger = logging.getLogger(__name__)


def is_distance_valid(raw_distance: float, doc_id: str) -> bool:
    """
    Geometric Guard: Unconditionally traps IEEE 754 NaN or Inf values.
    Dictates to the calling evaluation query loops if the document has to be evicted.

    :param raw_distance: Distance extracted from raw sequence query results matrix as float.
    :param doc_id: Unique database document identifier string context.
    :return: False if the document violates IEEE 754 geometric_guards rules, True otherwise.
    """
    if math.isnan(raw_distance) or math.isinf(raw_distance):
        logger.warning(
            f"Evicting document '{doc_id}' from semantic result pool "
            f"due to critical IEEE 754 geometric anomaly (distance: {raw_distance})."
        )
        return False
    return True


def clamp_distance_result(raw_distance: float, doc_id: str, metric: str) -> float | None:
    """
    Geometric Guards: Applies hardware-level boundary clamping to absorb floating-point approximations.

    If raw_distance is mathematically clampable according to the database index metric rules,
    returns the universally normalized similarity index baseline score (0.0 to 1.0), else returns None.

    :param raw_distance: Distance extracted from vector database sequence results as float.
    :param doc_id: Unique database document identifier string context.
    :param metric: Tensor space distance calculation layout type (COSINE, IP, L2).
    :return: Normalized similarity float (0.0 to 1.0) or None if document has to be evicted to prevent LLM aberrations.
    """
    metric_upper = metric.upper()

    match metric_upper:
        case "COSINE" | "IP":
            # 1. Macro-boundary verification to filter severe anomalies or ledger corruptions
            if raw_distance < -0.001 or raw_distance > 2.001:
                logger.warning(
                    f"Evicting document '{doc_id}' from result pool. "
                    f"Out of bounds {metric_upper} distance detected: {raw_distance}"
                )
                return None

            # 2. Hardware clamping: absorbs floating-point machine epsilon approximations (e.g. 2.000000004 -> 2.0)
            clamped_distance = max(0.0, min(2.0, raw_distance))
            normalized_similarity = 1.0 - (clamped_distance / 2.0)

        case "L2":
            # L2 Euclidean metric space starts at 0.0 but has no theoretical upper bound boundary
            if raw_distance < -0.001:
                logger.warning(
                    f"Evicting document '{doc_id}' from result pool. "
                    f"Impossible negative L2 distance: {raw_distance}"
                )
                return None

            clamped_distance = max(0.0, raw_distance)
            normalized_similarity = 1.0 / (1.0 + clamped_distance)

        case _:
            raise RuntimeError(f"Unsupported database structural index metric: {metric}")

    return normalized_similarity