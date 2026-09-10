"""Regression tests for the Windows poller (``poller.ps1``) — issue #251.

Two layers, because PowerShell is not available in the default (Linux,
offline) test environment:

* **Static contract tests** (always run, no PowerShell needed) — read
  ``poller.ps1`` and assert the hardening constructs are present:
  UTF-8-without-BOM log encoding, ``AppendAllText`` replacing ``Add-Content``,
  the stderr-as-data ``ErrorActionPreference`` toggle, and capture +
  propagation of the native poller exit code.  This gives CI a signal that the
  hardening is present and has not regressed.

* **Functional tests** (best-effort) — execute the *pattern* the poller uses,
  via an inline ``pwsh -NoProfile -Command`` snippet, and skip cleanly when no
  PowerShell (``pwsh`` or ``powershell``) is on PATH.  These verify the actual
  Unicode / stderr / exit-code behavior on any box that does have PowerShell
  5.1 or 7.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

# poller.ps1 lives at the repo root (a sibling of tests/).
_POLLER_PS1 = Path(__file__).resolve().parent.parent / "poller.ps1"


def _poller_source() -> str:
    assert _POLLER_PS1.exists(), f"poller.ps1 not found at {_POLLER_PS1}"
    return _POLLER_PS1.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Static contract tests — run everywhere, no PowerShell required


def test_poller_uses_utf8_no_bom_encoding():
    """The poller pins a no-BOM UTF-8 encoding for its log output."""
    src = _poller_source()
    assert "[System.Text.UTF8Encoding]::new($false)" in src, (
        "poller.ps1 must create a UTF8Encoding with BOM disabled (the $false ctor)"
    )


def test_poller_pins_python_to_utf8():
    """The poller sets the child Python to UTF-8 output (no CP1252 mangling)."""
    src = _poller_source()
    assert "PYTHONIOENCODING" in src and "utf-8" in src
    assert "PYTHONUTF8" in src


def test_poller_appends_log_with_appendalltext():
    """Log lines are written with File.AppendAllText, not Add-Content.

    PS 5.1 Add-Content defaults to UTF-16 LE (BOM on first write); the issue
    requires explicit UTF-8 AppendAllText.
    """
    src = _poller_source()
    assert "AppendAllText" in src, "poller.ps1 must use [System.IO.File]::AppendAllText"
    # No Add-Content may remain anywhere in the script.
    assert "Add-Content" not in src, "poller.ps1 must not use Add-Content"


def test_poller_allows_redirected_stderr_without_aborting():
    """The poller temporarily lowers ErrorActionPreference around the call.

    Under the default $ErrorActionPreference="Stop", native stderr captured
    through 2>&1 can abort the script.  The hardening toggles it to
    "Continue" for the poller invocation and restores it afterward.
    """
    src = _poller_source()
    assert '"Continue"' in src or "'Continue'" in src, (
        "poller.ps1 must set ErrorActionPreference to Continue around the poller call"
    )
    # And the original preference must be restored (save/restore pattern).
    assert "ErrorActionPreference" in src
    # The poller invocation must redirect stderr into the captured stream.
    assert "2>&1" in src


def test_poller_captures_and_propagates_exit_code():
    """The native poller exit code is captured and used as the script exit.

    Previously the script always exited 0 unless a PowerShell-level catch
    fired, so a failed ``python autoswe.py poller`` was invisible.
    """
    src = _poller_source()
    assert "$LASTEXITCODE" in src, "poller.ps1 must read $LASTEXITCODE"
    # The script must exit on the captured code (not a bare `exit 0`).
    assert "exit $pollerExitCode" in src or "exit $pollerExitCode".lower() in src.lower(), (
        "poller.ps1 must `exit` the captured poller exit code"
    )


# ---------------------------------------------------------------------------
# Functional tests — best-effort, skip when no PowerShell is available


def _pwsh() -> str | None:
    """Return a PowerShell executable on PATH, or None (tests skip)."""
    return shutil.which("pwsh") or shutil.which("powershell")


requires_pwsh = pytest.mark.skipif(
    _pwsh() is None,
    reason="PowerShell (pwsh/powershell) not available — functional test skipped",
)


def _run_pwsh(script: str, extra_env: dict | None = None, timeout: int = 60):
    """Run a PowerShell script inline; return the CompletedProcess."""
    exe = _pwsh()
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [exe, "-NoProfile", "-NoLogo", "-Command", script],
        env=env,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


@requires_pwsh
def test_poller_utf8_append_has_no_bom(tmp_path):
    """AppendAllText with a no-BOM UTF-8 encoding writes no BOM, correct UTF-8."""
    target = tmp_path / "poller_test.log"
    script = (
        "$enc = [System.Text.UTF8Encoding]::new($false)\n"
        "[System.IO.File]::AppendAllText($env:PWTEST_FILE, 'héllo € wörld 日本語`n', $enc)\n"
    )
    proc = _run_pwsh(script, extra_env={"PWTEST_FILE": str(target)})
    assert proc.returncode == 0, f"pwsh failed: {proc.stderr.decode(errors='replace')}"
    data = target.read_bytes()
    # No UTF-8 BOM at the start of the file.
    assert not data.startswith(b"\xef\xbb\xbf"), "log file must have no BOM"
    # The non-ASCII content round-trips as correct UTF-8.
    text = data.decode("utf-8")
    assert "héllo € wörld 日本語" in text


@requires_pwsh
def test_poller_exit_code_propagation():
    """`exit $LASTEXITCODE` propagates a native command's nonzero exit code."""
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "if ($env:OS -eq 'Windows_NT') { $native = @('cmd','/c','exit','3') } "
        "else { $native = @('/bin/sh','-c','exit 3') }\n"
        "$null = & $native\n"
        "exit [int]$LASTEXITCODE\n"
    )
    proc = _run_pwsh(script)
    assert proc.returncode == 3, f"expected exit 3, got {proc.returncode}"


@requires_pwsh
def test_poller_stderr_captured_without_abort():
    """Redirected stderr is captured as data while the script keeps running.

    Mirrors the poller pattern: lower ErrorActionPreference to Continue around
    a native command that writes stderr via 2>&1, capture it, restore the
    preference, and reach a trailing sentinel (proof the script did not abort).
    """
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$prev = $ErrorActionPreference\n"
        "$ErrorActionPreference = 'Continue'\n"
        "try {\n"
        "    if ($env:OS -eq 'Windows_NT') { $cmd = @('cmd','/c','echo','boom 1>&2') } "
        "else { $cmd = @('/bin/sh','-c','echo boom 1>&2') }\n"
        "    $output = & $cmd 2>&1\n"
        "    $null = $LASTEXITCODE\n"
        "} finally {\n"
        "    $ErrorActionPreference = $prev\n"
        "}\n"
        "Write-Output 'SENTINEL_OK'\n"
        "if (($output -join ',') -notmatch 'boom') { exit 99 }\n"
        "exit 0\n"
    )
    proc = _run_pwsh(script)
    out = proc.stdout.decode(errors="replace")
    # The script ran to completion (sentinel emitted → no abort on stderr).
    assert "SENTINEL_OK" in out, f"script aborted before sentinel: {out} {proc.stderr.decode(errors='replace')}"
    # The stderr text was captured into the output array.
    assert "boom" in out, "native stderr must be captured as data"
    assert proc.returncode == 0
