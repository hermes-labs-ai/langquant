"""Public-metadata claim guard.

The repository's public metadata surfaces (Zenodo deposit metadata, CITATION.cff,
README, pyproject) must not carry the retracted transfer-entropy result or the
n=74 mislabel beside the two-arm probe-score contrast. docs/EXPERIMENTS.md is the
one place that may discuss the retraction history, so it is excluded here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CLAIM_SURFACES = [".zenodo.json", "CITATION.cff", "README.md", "pyproject.toml"]

# A positive transfer-entropy claim (a TE number, "TE ≈ 0", or "Markov state"
# framing) is retracted; the phrase "transfer-entropy retraction" is allowed.
RETRACTED_PATTERNS = [
    re.compile(r"transfer entropy of\s*[0-9.]+", re.IGNORECASE),
    re.compile(r"\bTE\s*[≈~=]\s*0\b", re.IGNORECASE),
    re.compile(r"approximating a Markov state", re.IGNORECASE),
    re.compile(
        r"\b0\.846\b.{0,80}\bn\s*=\s*74\b|\bn\s*=\s*74\b.{0,80}\b0\.846\b",
        re.IGNORECASE | re.DOTALL,
    ),
]


def _cff_scalar(text: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*\"?([^\"\n]+)\"?\s*$", text, re.MULTILINE)
    assert match, f"CITATION.cff has no scalar '{key}'"
    return match.group(1).strip()


@pytest.mark.parametrize("relpath", CLAIM_SURFACES)
def test_claim_surface_has_no_retracted_result(relpath: str) -> None:
    text = (ROOT / relpath).read_text(encoding="utf-8")
    hits = [p.pattern for p in RETRACTED_PATTERNS if p.search(text)]
    assert not hits, f"{relpath} carries retracted claim pattern(s): {hits}"


def test_zenodo_metadata_matches_citation() -> None:
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert zenodo["title"] == _cff_scalar(cff, "title")
    assert zenodo["license"] == _cff_scalar(cff, "license")
    assert zenodo["creators"][0]["orcid"] == _cff_scalar(cff, "orcid").rsplit("/", 1)[-1]
    # The deposit description must restate the citation abstract's evidence
    # boundary, not a stronger claim.
    assert "documented as limitations" in zenodo["description"]
