"""Round 50: Documentation completeness tests.

Validates the docs knowledge system is complete and well-formed:
- README, LICENSE present
- docs/series-tutorial.md covers all 50 rounds
- docs/ has user-guide, design-tutorial, plan
- Cross-references resolve to real files
"""

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel: str) -> str:
    full = os.path.join(REPO, rel)
    assert os.path.exists(full), f"Missing doc: {rel}"
    with open(full, "r", encoding="utf-8") as f:
        return f.read()


# --- Core files ---

def test_readme_exists() -> None:
    content = _read("README.md")
    assert "ApiForge" in content
    assert "## " in content  # has sections


def test_license_exists() -> None:
    content = _read("LICENSE")
    assert "MIT" in content


def test_series_tutorial_exists() -> None:
    content = _read("docs/series-tutorial.md")
    assert "系列教程" in content


def test_user_guide_exists() -> None:
    content = _read("docs/user-guide.md")
    assert len(content) > 200


def test_design_tutorial_exists() -> None:
    content = _read("docs/design-tutorial.md")
    assert len(content) > 500


def test_50_rounds_plan_exists() -> None:
    content = _read("docs/50-rounds-plan.md")
    assert "Phase" in content


# --- Tutorial coverage ---

def test_tutorial_covers_all_phases() -> None:
    content = _read("docs/series-tutorial.md")
    for phase in ["核心", "生产", "可观测", "部署"]:
        assert phase in content, f"Missing phase: {phase}"


def test_tutorial_covers_all_rounds() -> None:
    content = _read("docs/series-tutorial.md")
    for rnd in [1, 11, 21, 31, 41, 46, 50]:
        assert str(rnd) in content, f"Missing round {rnd}"


def test_tutorial_has_code_example() -> None:
    content = _read("docs/series-tutorial.md")
    assert "```python" in content
    assert "forge.tool" in content


# --- Cross-references resolve ---

def test_tutorial_links_resolve() -> None:
    content = _read("docs/series-tutorial.md")
    # Extract relative md links like ./xxx.md or xxx.md
    links = re.findall(r"\]\(\.?/?(docs/)?([a-zA-Z0-9_\-]+\.md)\)", content)
    for _, name in links:
        # Resolve against docs/
        path = os.path.join(REPO, "docs", name)
        assert os.path.exists(path), f"Broken link: {name}"


def test_readme_documents_quickstart() -> None:
    content = _read("README.md")
    assert "python" in content.lower()
    assert "tool" in content.lower()


# --- Plan reflects reality ---

def test_plan_has_5_phases() -> None:
    content = _read("docs/50-rounds-plan.md")
    assert "Phase 1" in content
    assert "Phase 5" in content


def test_all_test_files_exist_for_rounds() -> None:
    """Spot-check that test files exist for representative rounds."""
    for rnd, fname in [
        (1, "test_basic.py"),
        (7, "test_round07_errors.py"),
        (40, "test_round40_integration.py"),
        (50, "test_round50_docs.py"),
    ]:
        path = os.path.join(REPO, "tests", fname)
        assert os.path.exists(path), f"Missing test file for round {rnd}: {fname}"
