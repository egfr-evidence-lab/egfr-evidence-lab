"""Numerical transformation only; assay eligibility is a separate curation step."""

import math


def ic50_to_pic50(value: float, unit: str, relation: str = "=") -> float:
    """Convert an exact, finite positive IC50 concentration to -log10(mol/L).

    Inequality/censored measurements must not become exact regression labels.
    This function does not decide whether two assays are comparable.
    """
    if relation.strip() != "=":
        raise ValueError("Only exact measurements (relation '=') are supported.")
    if isinstance(value, bool):
        raise ValueError("IC50 must be a finite positive number, not a boolean.")
    concentration = float(value)
    if not math.isfinite(concentration) or concentration <= 0:
        raise ValueError("IC50 must be finite and greater than zero.")
    normalized_unit = unit.strip().replace("μ", "u").replace("µ", "u")
    powers = {"M": 0, "mM": -3, "uM": -6, "nM": -9, "pM": -12}
    if normalized_unit not in powers:
        raise ValueError(f"Unsupported concentration unit: {unit!r}")
    return -math.log10(concentration) - powers[normalized_unit]
