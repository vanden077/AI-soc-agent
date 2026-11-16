from dataclasses import dataclass

@dataclass(frozen=True)
class VectorFieldSpecs:
    """
    [IMMUTABLE VECTOR SPECIFICATIONS]
    Represents the mathematical and structural fingerprint of an immutable vector field.
    """
    name: str
    dimension: int
    metric: str
    algorithm: str
    source_path: str