"""Tests for autoswe.harness.prompts — prompt override system.

Covers:
- _resolve_prompt_path: resolution logic for per-repo overrides
- load_plan_prompt / load_fix_prompt / load_review_prompt /
  load_conflict_resolution_prompt with repo_cfg
- build_*_prompt wiring of repo_cfg to the load_*_functions
"""

from pathlib import Path

from autoswe.harness.prompts import (
    _resolve_prompt_path,
)


def _patch_prompts_dir(tmp_path: Path, monkeypatch):
    """Monkeypatch AUTOSWE_DIR and _PROMPT_KEY_MAP to use the isolated dir.

    Must be called after creating tmp_path/config/prompts/.
    Returns the prompts module for convenience.
    """
    import autoswe.core.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "AUTOSWE_DIR", tmp_path)
    monkeypatch.setattr(cfg_mod, "PLAN_PROMPT_FILE", tmp_path / "config" / "prompts" / "plan.txt")
    monkeypatch.setattr(cfg_mod, "FIX_PROMPT_FILE", tmp_path / "config" / "prompts" / "fix.txt")
    monkeypatch.setattr(cfg_mod, "REVIEW_PROMPT_FILE", tmp_path / "config" / "prompts" / "review.txt")

    import autoswe.harness.prompts as prompts_mod

    monkeypatch.setattr(prompts_mod, "AUTOSWE_DIR", tmp_path)
    monkeypatch.setattr(
        prompts_mod, "_PROMPT_KEY_MAP",
        {
            "plan_prompt": tmp_path / "config" / "prompts" / "plan.txt",
            "fix_prompt": tmp_path / "config" / "prompts" / "fix.txt",
            "review_prompt": tmp_path / "config" / "prompts" / "review.txt",
            "conflict_resolution_prompt": tmp_path / "config" / "prompts" / "conflict_resolution.txt",
        },
    )
    return prompts_mod


# ---------------------------------------------------------------------------
# _resolve_prompt_path
# ---------------------------------------------------------------------------

def test_resolve_prompt_path_returns_bundled_default_when_no_repo_cfg():
    """Without repo_cfg, should return the bundled prompt file."""
    from autoswe.core.config import PLAN_PROMPT_FILE

    result = _resolve_prompt_path(None, "plan_prompt")
    assert result == PLAN_PROMPT_FILE


def test_resolve_prompt_path_returns_bundled_default_when_key_missing():
    """When repo_cfg lacks the key, should fall back to bundled default."""
    from autoswe.core.config import FIX_PROMPT_FILE

    result = _resolve_prompt_path({"base_branch": "main"}, "fix_prompt")
    assert result == FIX_PROMPT_FILE


def test_resolve_prompt_path_relative_path_resolved_against_autoswe_dir(
    isolated_autoswe_dir, monkeypatch,
):
    """Relative override paths should be resolved against AUTOSWE_DIR."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    result = _resolve_prompt_path(
        {"plan_prompt": "config/prompts/custom-plan.txt"},
        "plan_prompt",
    )
    assert result == isolated_autoswe_dir / "config" / "prompts" / "custom-plan.txt"


def test_resolve_prompt_path_absolute_path_used_as_is(
    isolated_autoswe_dir, monkeypatch,
):
    """Absolute override paths should be used as-is."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    custom_path = isolated_autoswe_dir / "my-prompts" / "custom-plan.txt"
    result = _resolve_prompt_path(
        {"plan_prompt": str(custom_path)},
        "plan_prompt",
    )
    assert result == custom_path


def test_resolve_prompt_path_all_keys():
    """All four prompt keys should resolve correctly."""
    import autoswe.harness.prompts as prompts_mod
    from autoswe.core.config import (
        FIX_PROMPT_FILE,
        PLAN_PROMPT_FILE,
        REVIEW_PROMPT_FILE,
    )

    repo_cfg = {}
    assert _resolve_prompt_path(repo_cfg, "plan_prompt") == PLAN_PROMPT_FILE
    assert _resolve_prompt_path(repo_cfg, "fix_prompt") == FIX_PROMPT_FILE
    assert _resolve_prompt_path(repo_cfg, "review_prompt") == REVIEW_PROMPT_FILE
    assert _resolve_prompt_path(repo_cfg, "conflict_resolution_prompt") == prompts_mod.CONFLICT_RESOLUTION_PROMPT_FILE


# ---------------------------------------------------------------------------
# load_plan_prompt with overrides
# ---------------------------------------------------------------------------

def test_load_plan_prompt_returns_bundled_default(isolated_autoswe_dir, monkeypatch):
    """Without override, should load from bundled plan.txt."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "plan.txt").write_text("BUNDLED PLAN PROMPT")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    # Must re-import after monkeypatch to pick up new _PROMPT_KEY_MAP
    from autoswe.harness.prompts import load_plan_prompt as lpp

    result = lpp()
    assert result == "BUNDLED PLAN PROMPT"


def test_load_plan_prompt_uses_repo_override(isolated_autoswe_dir, monkeypatch):
    """When repo_cfg contains plan_prompt, it should load from the override file."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "plan.txt").write_text("BUNDLED PLAN PROMPT")
    custom_prompt = prompt_dir / "custom-plan.txt"
    custom_prompt.write_text("CUSTOM PLAN PROMPT FOR THIS REPO")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_plan_prompt as lpp

    result = lpp(repo_cfg={"plan_prompt": str(custom_prompt)})
    assert result == "CUSTOM PLAN PROMPT FOR THIS REPO"
    assert "BUNDLED" not in result


def test_load_plan_prompt_override_missing_file_falls_back_to_bundled(
    isolated_autoswe_dir, monkeypatch,
):
    """When override path doesn't exist, should fall back to bundled default."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "plan.txt").write_text("BUNDLED PLAN PROMPT")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_plan_prompt as lpp

    result = lpp(repo_cfg={"plan_prompt": "/nonexistent/path/plan.txt"})
    assert result == "BUNDLED PLAN PROMPT"


def test_load_plan_prompt_relative_override_path(isolated_autoswe_dir, monkeypatch):
    """Relative path in repo_cfg should resolve against AUTOSWE_DIR."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "edgar-plan.txt").write_text("EDGAR-SPECIFIC PLAN PROMPT")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_plan_prompt as lpp

    result = lpp(repo_cfg={"plan_prompt": "config/prompts/edgar-plan.txt"})
    assert result == "EDGAR-SPECIFIC PLAN PROMPT"


# ---------------------------------------------------------------------------
# load_fix_prompt with overrides
# ---------------------------------------------------------------------------

def test_load_fix_prompt_uses_repo_override(isolated_autoswe_dir, monkeypatch):
    """When repo_cfg contains fix_prompt, it should load from the override file."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "fix.txt").write_text("BUNDLED FIX PROMPT")
    custom_prompt = prompt_dir / "custom-fix.txt"
    custom_prompt.write_text("CUSTOM FIX PROMPT")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_fix_prompt as lfp

    result = lfp(repo_cfg={"fix_prompt": str(custom_prompt)})
    assert result == "CUSTOM FIX PROMPT"
    assert "BUNDLED" not in result


def test_load_fix_prompt_no_override_uses_bundled(isolated_autoswe_dir, monkeypatch):
    """Without fix_prompt in repo_cfg, should use bundled file."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "fix.txt").write_text("BUNDLED FIX PROMPT")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_fix_prompt as lfp

    result = lfp(repo_cfg={"base_branch": "main"})
    assert result == "BUNDLED FIX PROMPT"


# ---------------------------------------------------------------------------
# load_review_prompt with overrides
# ---------------------------------------------------------------------------

def test_load_review_prompt_uses_repo_override(isolated_autoswe_dir, monkeypatch):
    """When repo_cfg contains review_prompt, it should load from the override file."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "review.txt").write_text("BUNDLED REVIEW PROMPT")
    custom_prompt = prompt_dir / "gstack-review.txt"
    custom_prompt.write_text("GSTACK-INSPIRED REVIEW PROMPT")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_review_prompt as lrp

    result = lrp(repo_cfg={"review_prompt": str(custom_prompt)})
    assert result == "GSTACK-INSPIRED REVIEW PROMPT"


# ---------------------------------------------------------------------------
# build_*_prompt wires repo_cfg to load_*_prompt
# ---------------------------------------------------------------------------

def test_build_plan_prompt_uses_custom_template(isolated_autoswe_dir, monkeypatch):
    """build_plan_prompt should use a custom plan template from repo_cfg."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    custom_file = prompt_dir / "custom-plan.txt"
    custom_file.write_text(
        "CUSTOM TEMPLATE for {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}\n"
        "{{BODY}}\n{{COMMENTS}}\n{{GUIDANCE_BLOCK}}\n{{REVIEW_BLOCK}}\n"
        "Branch: {{BASE_BRANCH}}"
    )
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import build_plan_prompt

    task = {
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test",
        "body": "Issue body",
        "base_branch": "main",
    }

    prompt = build_plan_prompt(
        task,
        repo_root="/tmp",
        comments=[],
        repo_cfg={"plan_prompt": str(custom_file)},
        guidance=None,
    )
    assert "CUSTOM TEMPLATE" in prompt
    assert "o/r#1" in prompt
    assert "Issue body" in prompt


def test_build_fix_prompt_uses_custom_template(isolated_autoswe_dir, monkeypatch):
    """build_fix_prompt should use a custom fix template from repo_cfg."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    custom_file = prompt_dir / "custom-fix.txt"
    custom_file.write_text(
        "CUSTOM FIX TEMPLATE for {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n"
        "{{BODY}}\n{{COMMENTS}}\n{{GUIDANCE_BLOCK}}\n{{PLAN}}\n{{REVIEW_BLOCK}}"
    )
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import build_fix_prompt

    task = {
        "owner": "o",
        "repo": "r",
        "issue_number": 2,
        "title": "Fix issue",
        "body": "Body text",
    }

    prompt = build_fix_prompt(
        task,
        repo_root="/tmp",
        comments=[],
        repo_cfg={"fix_prompt": str(custom_file)},
        guidance="be careful",
        plan_text="Do X",
    )
    assert "CUSTOM FIX TEMPLATE" in prompt
    assert "o/r#2: Fix issue" in prompt
    assert "Body text" in prompt


def test_build_review_prompt_uses_custom_template(isolated_autoswe_dir, monkeypatch):
    """build_review_prompt should use a custom review template from repo_cfg."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    custom_file = prompt_dir / "custom-review.txt"
    custom_file.write_text(
        "CUSTOM REVIEW for {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n"
        "{{BODY}}\n{{PLAN}}\n{{DIFF_STAT}}\n{{DIFF}}\n{{GUIDANCE_BLOCK}}\n"
        "Base: {{BASE_BRANCH}}"
    )
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import build_review_prompt

    task = {
        "owner": "o",
        "repo": "r",
        "issue_number": 3,
        "title": "Review me",
        "body": "Review body",
        "base_branch": "develop",
    }

    prompt = build_review_prompt(
        task,
        repo_root="/tmp",
        repo_cfg={"review_prompt": str(custom_file)},
        plan_text="Plan text",
        diff_stat="stat output",
        diff_text="diff output",
        guidance="review guidance",
    )
    assert "CUSTOM REVIEW" in prompt
    assert "o/r#3: Review me" in prompt
    assert "Review body" in prompt
    assert "Base: develop" in prompt


# ---------------------------------------------------------------------------
# End-to-end: repos.json shape → prompt loading
# ---------------------------------------------------------------------------

def test_full_repos_json_flow(isolated_autoswe_dir, monkeypatch):
    """Simulate the full flow: repos.json entry → load_prompt."""
    import autoswe.core.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "AUTOSWE_DIR", isolated_autoswe_dir)
    monkeypatch.setattr(cfg_mod, "REPOS_CONFIG_FILE", isolated_autoswe_dir / "config" / "repos.json")

    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    # Create a repos.json with custom prompts
    import json
    repos_file = isolated_autoswe_dir / "config" / "repos.json"
    repos_file.write_text(json.dumps({
        "natedorr/edgarFiling": {
            "provider": "github",
            "pat": "fake-token",
            "base_branch": "main",
            "plan_prompt": "config/prompts/edgar-plan.txt",
            "review_prompt": "config/prompts/edgar-review.txt",
            "fix_prompt": "config/prompts/edgar-fix.txt",
        },
    }))

    # Create the custom prompt files
    (prompt_dir / "edgar-plan.txt").write_text("EDGAR PLAN")
    (prompt_dir / "edgar-review.txt").write_text("EDGAR REVIEW")
    (prompt_dir / "edgar-fix.txt").write_text("EDGAR FIX")
    # Bundled defaults also exist
    (prompt_dir / "plan.txt").write_text("DEFAULT PLAN")
    (prompt_dir / "review.txt").write_text("DEFAULT REVIEW")
    (prompt_dir / "fix.txt").write_text("DEFAULT FIX")

    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.core.config import load_repos_config
    from autoswe.harness.prompts import (
        load_fix_prompt as lfp,
    )
    from autoswe.harness.prompts import (
        load_plan_prompt as lpp,
    )
    from autoswe.harness.prompts import (
        load_review_prompt as lrp,
    )

    repos_cfg = load_repos_config()
    repo_cfg = repos_cfg.get("natedorr/edgarFiling", {})

    assert lpp(repo_cfg) == "EDGAR PLAN"
    assert lfp(repo_cfg) == "EDGAR FIX"
    assert lrp(repo_cfg) == "EDGAR REVIEW"


def test_repo_without_prompt_overrides_uses_defaults(
    isolated_autoswe_dir, monkeypatch,
):
    """A repo not listed in repos.json should use bundled defaults."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "plan.txt").write_text("DEFAULT PLAN")
    (prompt_dir / "fix.txt").write_text("DEFAULT FIX")
    (prompt_dir / "review.txt").write_text("DEFAULT REVIEW")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import (
        load_fix_prompt as lfp,
    )
    from autoswe.harness.prompts import (
        load_plan_prompt as lpp,
    )
    from autoswe.harness.prompts import (
        load_review_prompt as lrp,
    )

    # Empty repo_cfg → should use defaults
    assert lpp({}) == "DEFAULT PLAN"
    assert lfp({}) == "DEFAULT FIX"
    assert lrp({}) == "DEFAULT REVIEW"


# ---------------------------------------------------------------------------
# load_conflict_resolution_prompt with overrides
# ---------------------------------------------------------------------------

def test_load_conflict_resolution_prompt_uses_repo_override(
    isolated_autoswe_dir, monkeypatch,
):
    """When repo_cfg contains conflict_resolution_prompt, it should load from the override."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "conflict_resolution.txt").write_text("BUNDLED CONFLICT RESOLUTION")
    custom_prompt = prompt_dir / "custom-conflict.txt"
    custom_prompt.write_text("CUSTOM CONFLICT RESOLUTION")
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import load_conflict_resolution_prompt as lcrc

    result = lcrc(repo_cfg={"conflict_resolution_prompt": str(custom_prompt)})
    assert result == "CUSTOM CONFLICT RESOLUTION"


def test_build_conflict_resolution_prompt_uses_custom_template(
    isolated_autoswe_dir, monkeypatch,
):
    """build_conflict_resolution_prompt should use a custom template from repo_cfg."""
    prompt_dir = isolated_autoswe_dir / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    custom_file = prompt_dir / "custom-conflict.txt"
    custom_file.write_text(
        "CUSTOM CONFLICT for {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n"
        "{{BODY}}\n{{PLAN}}\n{{CONFLICT_FILES}}\nBranch: {{BASE_BRANCH}}"
    )
    _patch_prompts_dir(isolated_autoswe_dir, monkeypatch)

    from autoswe.harness.prompts import build_conflict_resolution_prompt

    task = {"owner": "o", "repo": "r", "issue_number": 4, "title": "Conflict", "body": "Body"}

    prompt = build_conflict_resolution_prompt(
        task, ["foo.py"], plan_text="Plan", base_branch="main",
        repo_cfg={"conflict_resolution_prompt": str(custom_file)},
    )
    assert "CUSTOM CONFLICT" in prompt
    assert "o/r#4: Conflict" in prompt
    assert "foo.py" in prompt
    assert "Plan" in prompt


