"""Security regression tests for TASK-01: eliminate shell injection in git/pip helpers.

These tests verify that the previously-vulnerable ``os.system(...)`` calls in
the five Architecture-Gate-affected files have been replaced by safe
``subprocess.run([...], check=True)`` argument-list invocations.

Scope (per Architecture Gate):
  - packages/file_processor/config.py
  - packages/handwriting/config.py
  - packages/omnifile/config.py
  - apps/handwriting-demo/variants/handwriting-ocr/config.py
  - apps/handwriting-demo/variants/handwriting-ocr/main.py

What these tests verify (behavior, not syntax):
  1. No ``os.system(`` call remains in any in-scope file.
  2. No ``shell=True`` appears in any in-scope file.
  3. ``OmniFileConfig.setup_environment`` invokes ``subprocess.run`` with a
     list argument (never a string), with ``check=True``, and never with
     ``shell=True``.
  4. Malicious-looking ``github_username`` / ``github_email`` values are
     passed through as data — they appear verbatim as a single list element
     rather than being interpolated into a shell string.
  5. The ``run_colab_setup`` pip-install path in main.py uses
     ``subprocess.run([...], check=True)`` with the requirements file path
     passed as a separate argument.
  6. End-to-end: a real ``git config --global user.name`` invocation, run
     with an isolated temporary ``HOME``, stores a malicious-looking value
     literally — proving no shell interpretation took place.

No test in this file ever modifies the developer's real ``~/.gitconfig``.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]

# The five files explicitly enumerated by the Architecture Gate.
IN_SCOPE_FILES: list[Path] = [
    ROOT / "packages" / "file_processor" / "config.py",
    ROOT / "packages" / "handwriting" / "config.py",
    ROOT / "packages" / "omnifile" / "config.py",
    ROOT / "apps" / "handwriting-demo" / "variants" / "handwriting-ocr" / "config.py",
    ROOT / "apps" / "handwriting-demo" / "variants" / "handwriting-ocr" / "main.py",
]

IN_SCOPE_CONFIG_FILES: list[Path] = [p for p in IN_SCOPE_FILES if p.name == "config.py"]
MAIN_FILE: Path = ROOT / "apps" / "handwriting-demo" / "variants" / "handwriting-ocr" / "main.py"

# Malicious-looking test values. None of these would be destructive even if
# they were accidentally executed (no rm/touch/cat that writes outside /tmp
# or that exfiltrates data). They exist to prove the values are passed as
# data, not interpreted as shell.
MALICIOUS_USER = '"; echo PWNED; #'
MALICIOUS_EMAIL = "$(echo PWNED)"
BACKTICK_VALUE = "`echo PWNED`"
PIPE_VALUE = "| echo PWNED"
AMP_VALUE = "&& echo PWNED"


# ---------------------------------------------------------------------------
# 1) Static source-level checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("file_path", IN_SCOPE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_os_system_in_in_scope_files(file_path: Path) -> None:
    """None of the five in-scope files may contain ``os.system(`` anymore."""
    source = file_path.read_text(encoding="utf-8")
    assert "os.system(" not in source, (
        f"{file_path} still contains os.system( — TASK-01 regression"
    )
    assert "os.system (" not in source, (
        f"{file_path} still contains os.system ( — TASK-01 regression"
    )


@pytest.mark.parametrize("file_path", IN_SCOPE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_shell_true_in_in_scope_files(file_path: Path) -> None:
    """None of the five in-scope files may use ``shell=True``."""
    source = file_path.read_text(encoding="utf-8")
    assert "shell=True" not in source, (
        f"{file_path} contains shell=True — TASK-01 regression"
    )
    assert "shell =True" not in source


@pytest.mark.parametrize("file_path", IN_SCOPE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_subprocess_imported_where_needed(file_path: Path) -> None:
    """Each in-scope file must import ``subprocess`` if it now calls ``subprocess.run``."""
    source = file_path.read_text(encoding="utf-8")
    if "subprocess.run(" in source:
        assert "import subprocess" in source, (
            f"{file_path} calls subprocess.run but does not import subprocess"
        )


# ---------------------------------------------------------------------------
# Helper: load each config.py as an isolated module (they all define a
# class named ``OmniFileConfig`` so we cannot import them by package name).
# ---------------------------------------------------------------------------

def _load_config_module(file_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_main_module(file_path: Path, module_name: str):
    """Load main.py as an isolated module.

    ``main.py`` has a top-level ``sys.path.insert(0, str(PROJECT_ROOT))``
    side-effect that pollutes the rest of the test session (the inserted
    directory contains an ``app.py`` that shadows the project's real
    ``app/`` package for downstream tests). We snapshot ``sys.path`` and
    ``sys.modules['app']`` before loading and restore them afterward so
    no pollution leaks into subsequent tests.
    """
    saved_path = list(sys.path)
    saved_app = sys.modules.get("app", None)
    saved_app_services = sys.modules.get("app.services", None)

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        # Restore sys.path to its pre-load state so the apps/... directory
        # is no longer on sys.path. The loaded module's PROJECT_ROOT is
        # already captured and is independent of sys.path.
        sys.path[:] = saved_path
        # If loading main.py pulled in an ``app`` module (e.g., via
        # accidental transitive imports), evict it so downstream tests
        # don't see a stale/shadowed ``app`` module.
        if saved_app is None:
            sys.modules.pop("app", None)
        else:
            sys.modules["app"] = saved_app
        if saved_app_services is None:
            sys.modules.pop("app.services", None)
        else:
            sys.modules["app.services"] = saved_app_services
    return module


# ---------------------------------------------------------------------------
# 2) Behavioral tests for the four config.py files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path",
    IN_SCOPE_CONFIG_FILES,
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_setup_environment_invokes_subprocess_run_with_list_and_check(
    file_path: Path, tmp_path: Path
) -> None:
    """``setup_environment`` must call ``subprocess.run`` with a list argv
    (never a string), with ``check=True``, and never ``shell=True``."""
    module = _load_config_module(file_path, f"cfg_{file_path.stem}_{file_path.parent.name}")
    cfg = module.OmniFileConfig(
        project_root=str(tmp_path),
        github_username=MALICIOUS_USER,
        github_email=MALICIOUS_EMAIL,
        hf_token="",  # avoid mutating real os.environ
    )

    # Snapshot/restore os.environ so setup_environment's env mutations
    # (TRANSFORMERS_CACHE, TORCH_HOME, HF_HOME, etc.) don't leak to
    # other tests in the same session.
    with mock.patch.dict(os.environ, {}, clear=False), \
         mock.patch.object(module.subprocess, "run") as mock_run:
        cfg.setup_environment()

    assert mock_run.called, "subprocess.run was not called at all"
    # Inspect every call
    for call in mock_run.call_args_list:
        args, kwargs = call
        # First positional arg must be a list, not a string
        assert args, "subprocess.run called with no positional arguments"
        argv = args[0]
        assert isinstance(argv, list), (
            f"subprocess.run argv must be a list, got {type(argv).__name__}"
        )
        assert all(isinstance(x, str) for x in argv), (
            "subprocess.run argv must contain only strings"
        )
        # check=True required by TASK-01 preferred pattern
        assert kwargs.get("check") is True, (
            f"subprocess.run must be called with check=True; got kwargs={kwargs}"
        )
        # shell=True forbidden
        assert kwargs.get("shell") in (None, False), (
            f"subprocess.run must not be called with shell=True; got kwargs={kwargs}"
        )


@pytest.mark.parametrize(
    "file_path",
    IN_SCOPE_CONFIG_FILES,
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_setup_environment_passes_malicious_values_as_data_not_shell(
    file_path: Path, tmp_path: Path
) -> None:
    """A malicious ``github_username`` / ``github_email`` must survive as a
    single list element (data), not be interpolated into a shell string."""
    module = _load_config_module(file_path, f"cfg2_{file_path.stem}_{file_path.parent.name}")
    cfg = module.OmniFileConfig(
        project_root=str(tmp_path),
        github_username=MALICIOUS_USER,
        github_email=MALICIOUS_EMAIL,
        hf_token="",
    )

    with mock.patch.dict(os.environ, {}, clear=False), \
         mock.patch.object(module.subprocess, "run") as mock_run:
        cfg.setup_environment()

    # Collect every argv list passed to subprocess.run
    argvs: list[list[str]] = []
    for call in mock_run.call_args_list:
        args, _ = call
        argvs.append(args[0])

    # We expect at least three calls: user.name, user.email, init.defaultBranch
    assert len(argvs) >= 3, (
        f"expected >=3 subprocess.run calls, got {len(argvs)}"
    )

    # Find the user.name and user.email calls
    name_calls = [a for a in argvs if "user.name" in a]
    email_calls = [a for a in argvs if "user.email" in a]
    assert name_calls, "no `git config user.name` call observed"
    assert email_calls, "no `git config user.email` call observed"

    # The malicious value must appear as a single, intact list element.
    # If shell interpolation had happened, the value would have been broken
    # into separate words or escaped.
    name_argv = name_calls[0]
    assert MALICIOUS_USER in name_argv, (
        f"malicious username not found verbatim in argv {name_argv}"
    )
    # The malicious value must be the LAST element of the argv (the value
    # position for `git config --global user.name <value>`).
    assert name_argv[-1] == MALICIOUS_USER, (
        f"username must occupy the value slot; got argv={name_argv}"
    )

    email_argv = email_calls[0]
    assert MALICIOUS_EMAIL in email_argv, (
        f"malicious email not found verbatim in argv {email_argv}"
    )
    assert email_argv[-1] == MALICIOUS_EMAIL, (
        f"email must occupy the value slot; got argv={email_argv}"
    )

    # The argv must NOT contain extra tokens like "echo", "PWNED", ";", "$("
    # as separate elements — the malicious string is one piece of data.
    for argv in argvs:
        # An attacker-style shell string would contain "echo PWNED" as a
        # separate token after a semicolon. Because we pass argv as a list,
        # the only occurrence of "PWNED" should be inside the malicious
        # value element, NOT as a standalone shell command word.
        standalone_pwned = [tok for tok in argv if tok == "echo" or tok == "PWNED"]
        assert not standalone_pwned, (
            f"shell command tokens leaked into argv: {argv}"
        )


@pytest.mark.parametrize(
    "file_path",
    IN_SCOPE_CONFIG_FILES,
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_setup_environment_does_not_call_os_system(
    file_path: Path, tmp_path: Path
) -> None:
    """``setup_environment`` must never invoke ``os.system`` (the legacy path)."""
    module = _load_config_module(file_path, f"cfg3_{file_path.stem}_{file_path.parent.name}")
    cfg = module.OmniFileConfig(
        project_root=str(tmp_path),
        github_username="safe_user",
        github_email="safe@example.com",
        hf_token="",
    )
    with mock.patch.dict(os.environ, {}, clear=False), \
         mock.patch("os.system") as mock_os_system, \
         mock.patch.object(module.subprocess, "run") as mock_run:
        cfg.setup_environment()
    mock_os_system.assert_not_called()
    assert mock_run.called


@pytest.mark.parametrize(
    "malicious_value",
    [
        MALICIOUS_USER,
        MALICIOUS_EMAIL,
        BACKTICK_VALUE,
        PIPE_VALUE,
        AMP_VALUE,
    ],
    ids=["semicolon-echo", "dollar-paren", "backtick", "pipe", "ampersand"],
)
def test_setup_environment_handles_all_metacharacter_classes(
    malicious_value: str, tmp_path: Path
) -> None:
    """Smoke-test all five metacharacter classes against one config file
    (file_processor/config.py, the canonical instance)."""
    file_path = ROOT / "packages" / "file_processor" / "config.py"
    module = _load_config_module(file_path, "cfg_meta")
    cfg = module.OmniFileConfig(
        project_root=str(tmp_path),
        github_username=malicious_value,
        github_email=malicious_value,
        hf_token="",
    )
    with mock.patch.dict(os.environ, {}, clear=False), \
         mock.patch.object(module.subprocess, "run") as mock_run:
        cfg.setup_environment()
    # Every call must pass the malicious value as a single intact list element
    for call in mock_run.call_args_list:
        args, _ = call
        argv = args[0]
        # No shell=True
        # If this argv is a user.name / user.email call, the value must be intact
        if "user.name" in argv or "user.email" in argv:
            assert argv[-1] == malicious_value, (
                f"malicious value not preserved intact: argv={argv}"
            )


# ---------------------------------------------------------------------------
# 3) Behavioral tests for main.py (pip install path)
# ---------------------------------------------------------------------------

def test_main_module_has_no_os_system() -> None:
    """The main.py file must no longer call os.system."""
    source = MAIN_FILE.read_text(encoding="utf-8")
    assert "os.system" not in source


def test_main_module_imports_subprocess() -> None:
    """main.py must import subprocess (replacing the old ``import os``)."""
    source = MAIN_FILE.read_text(encoding="utf-8")
    assert "import subprocess" in source


def test_run_colab_setup_uses_subprocess_run_with_list_when_requirements_present(
    tmp_path: Path,
) -> None:
    """When ``requirements.txt`` exists, ``run_colab_setup`` must invoke
    ``pip install -q -r <path>`` via ``subprocess.run`` with the path as a
    separate list argument (never interpolated into a shell string)."""
    # Load main.py from its real location so PROJECT_ROOT points at the
    # real apps/handwriting-demo/variants/handwriting-ocr/ directory.
    module = _load_main_module(MAIN_FILE, "main_under_test")
    # Force PROJECT_ROOT to a temp dir we control and drop a fake
    # requirements.txt there so the if-branch is taken.
    fake_root = tmp_path
    (fake_root / "requirements.txt").write_text("# fake\n", encoding="utf-8")

    with mock.patch.object(module, "PROJECT_ROOT", fake_root), \
         mock.patch.object(module.subprocess, "run") as mock_run:
        module.run_colab_setup()

    # Find the pip install call
    pip_calls = [
        call for call in mock_run.call_args_list
        if call.args and "pip" in call.args[0]
    ]
    assert pip_calls, "no pip install subprocess.run call observed"
    pip_call = pip_calls[0]
    argv = pip_call.args[0]
    assert isinstance(argv, list)
    assert "pip" in argv
    assert "install" in argv
    assert "-r" in argv
    # The requirements file path must be a single list element, not
    # interpolated into a shell string.
    req_path_idx = argv.index("-r") + 1
    assert req_path_idx < len(argv), "missing path after -r"
    # Path must point at our fake requirements.txt
    assert str(fake_root / "requirements.txt") == argv[req_path_idx]
    # check=True required
    assert pip_call.kwargs.get("check") is True
    # shell=True forbidden
    assert pip_call.kwargs.get("shell") in (None, False)


def test_run_colab_setup_uses_subprocess_run_with_list_when_requirements_absent(
    tmp_path: Path,
) -> None:
    """When ``requirements.txt`` does not exist, ``run_colab_setup`` must
    invoke the fallback ``pip install -q <packages...>`` via ``subprocess.run``
    with each package as a separate list element."""
    module = _load_main_module(MAIN_FILE, "main_under_test_no_req")

    # Temp dir without requirements.txt
    fake_root = tmp_path / "noreq"
    fake_root.mkdir()

    with mock.patch.object(module, "PROJECT_ROOT", fake_root), \
         mock.patch.object(module.subprocess, "run") as mock_run:
        module.run_colab_setup()

    pip_calls = [
        call for call in mock_run.call_args_list
        if call.args and "pip" in call.args[0]
    ]
    assert pip_calls, "no pip install subprocess.run call observed"
    pip_call = pip_calls[0]
    argv = pip_call.args[0]
    assert isinstance(argv, list)
    assert "pip" in argv
    assert "install" in argv
    # All package names must be individual list elements (no shell string)
    for pkg in ("streamlit", "pandas", "numpy", "Pillow",
                "opencv-python-headless", "easyocr", "PyMuPDF",
                "transformers", "torch"):
        assert pkg in argv, f"package {pkg!r} missing from argv {argv}"
    # check=True required
    assert pip_call.kwargs.get("check") is True
    # shell=True forbidden
    assert pip_call.kwargs.get("shell") in (None, False)


# ---------------------------------------------------------------------------
# 4) End-to-end: real git config stores malicious value literally
# ---------------------------------------------------------------------------

def test_real_git_config_stores_malicious_value_literally(tmp_path: Path) -> None:
    """End-to-end proof: actually invoke ``git config --global user.name``
    via the new ``subprocess.run([...], check=True)`` path, against an
    isolated temporary HOME, then read the stored value back.

    If shell interpretation were happening, the malicious value would NOT
    be stored verbatim — instead, the shell would have executed the
    embedded command and the stored value would be a mangled fragment.

    This test does NOT modify the developer's real ``~/.gitconfig``: it
    isolates HOME and GIT_CONFIG_GLOBAL to a temporary directory.
    """
    file_path = ROOT / "packages" / "file_processor" / "config.py"
    module = _load_config_module(file_path, "cfg_e2e")

    # Use a unique value that we can grep for in the resulting git config.
    sentinel = '"; echo PWNED_' + "TASK01" + '; #'

    # Isolated environment: redirect HOME and GIT_CONFIG_GLOBAL to tmp_path
    # so the real ~/.gitconfig is never touched.
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    git_config_file = fake_home / ".gitconfig"

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["GIT_CONFIG_GLOBAL"] = str(git_config_file)

    # Patch the module's subprocess.run so that, when it invokes git config,
    # we delegate to the real subprocess.run with our isolated env. This
    # exercises the actual subprocess.run([...], check=True) call site
    # without allowing it to touch the real user environment.
    real_run = subprocess.run

    def _isolated_run(argv, **kwargs):
        # Force the isolated environment
        kwargs.setdefault("env", env)
        kwargs["env"] = env
        # Block shell=True defensively even though the source no longer uses it
        assert kwargs.get("shell") in (None, False), "shell=True is forbidden"
        # Strip check from our delegate (we'll check exit code ourselves)
        check = kwargs.pop("check", False)
        result = real_run(argv, **kwargs)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, argv, output=result.stdout, stderr=result.stderr
            )
        return result

    # Build a config that uses the malicious sentinel
    cfg = module.OmniFileConfig(
        project_root=str(tmp_path / "project"),
        github_username=sentinel,
        github_email=sentinel,
        hf_token="",
    )

    with mock.patch.dict(os.environ, {}, clear=False), \
         mock.patch.object(module.subprocess, "run", side_effect=_isolated_run):
        cfg.setup_environment()

    # Read back the stored git config
    assert git_config_file.exists(), "git config file was not created"
    stored = git_config_file.read_text(encoding="utf-8")
    # The malicious sentinel must appear VERBATIM in the stored config —
    # i.e., it was passed as data, not interpreted as a shell command.
    assert sentinel in stored, (
        f"sentinel {sentinel!r} not found verbatim in git config; "
        f"shell interpretation may have occurred. stored config:\n{stored}"
    )
    # No "PWNED_TASK01" marker should appear as a side-effect of an
    # executed shell command (it would have been echoed to stdout, not
    # stored in git config). The marker must only appear as part of the
    # sentinel value, which is itself stored as user.name/user.email.
    # We cannot easily inspect stdout from here, but if shell injection
    # had happened, git config would have stored the mangled result
    # (e.g., empty or partial). The verbatim presence of the sentinel
    # is sufficient proof.


def test_real_pip_install_argv_passes_malicious_path_safely(tmp_path: Path) -> None:
    """End-to-end-ish proof for the main.py pip-install path: if the
    requirements file path contained a shell metacharacter, it must
    still be passed as a single list element, not interpreted by a shell.
    """
    file_path = MAIN_FILE
    module = _load_main_module(file_path, "main_e2e")

    # Drop a fake requirements.txt whose NAME contains shell metacharacters.
    # (We use a directory name with a leading space, which would break
    # naive shell quoting but is perfectly safe as a subprocess argv.)
    bad_dir = tmp_path / "evil; echo PWNED; #"
    bad_dir.mkdir()
    fake_req = bad_dir / "requirements.txt"
    fake_req.write_text("# fake\n", encoding="utf-8")

    captured_argv: list[list[str]] = []

    def _capture(argv, **kwargs):
        captured_argv.append(list(argv))
        # Pretend success
        return mock.MagicMock(returncode=0)

    with mock.patch.object(module, "PROJECT_ROOT", bad_dir), \
         mock.patch.object(module.subprocess, "run", side_effect=_capture):
        module.run_colab_setup()

    # Find the pip install -r call
    pip_calls = [a for a in captured_argv if "pip" in a and "-r" in a]
    assert pip_calls, "no pip install -r call captured"
    argv = pip_calls[0]
    # The path with shell metacharacters must be a single list element
    req_path_idx = argv.index("-r") + 1
    assert req_path_idx < len(argv)
    assert argv[req_path_idx] == str(fake_req)
    # And the shell metacharacters are preserved verbatim, not interpreted
    assert "echo PWNED" not in argv  # would only appear if shell-split
    assert ";" not in argv  # the semicolon lives inside the path string only
