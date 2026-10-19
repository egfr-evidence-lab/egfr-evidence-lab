"""Validate the scientific scope of the scaffold, not data or model quality."""

import json
import math
from pathlib import Path


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    try:
        target = config["target"]
        curation = config["curation"]
        evaluation = config["evaluation"]
        agent = config["agent"]
        if target["chembl_id"] != "CHEMBL203" or target["endpoint"] != "IC50":
            raise ValueError("This scaffold is scoped to EGFR IC50.")
        if target["label"] != "pIC50":
            raise ValueError("The regression label must be pIC50.")
        if curation["relation"] != "=":
            raise ValueError("Exact-value regression requires relation '='.")
        if curation["unknown_variant_is_wild_type"] is not False:
            raise ValueError("Unresolved variant metadata must not imply wild type.")
        if curation["pool_cell_and_biochemical_assays"] is not False:
            raise ValueError("Cell and biochemical assays require separate cohorts.")
        if curation["pool_ic50_ki_kd"] is not False:
            raise ValueError("Do not pool IC50, Ki and Kd as one label.")
        fractions = evaluation["fractions"]
        if (
            len(fractions) != 3
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) or not 0 < x < 1 for x in fractions)
            or not math.isclose(sum(fractions), 1.0)
        ):
            raise ValueError("Provide three positive split fractions summing to one.")
        if evaluation["primary_split"] != "scaffold":
            raise ValueError("The primary evaluation must use scaffold groups.")
        if evaluation["test_used_for_tuning"] is not False:
            raise ValueError("Final test data must not be used for tuning.")
        if agent["require_source_ids"] is not True:
            raise ValueError("Literature claims require source identifiers.")
        if agent["llm_may_invent_measurements"] is not False:
            raise ValueError("Measurements must come from data, not LLM generation.")
    except KeyError as exc:
        raise ValueError(f"Missing configuration field: {exc.args[0]}") from exc
