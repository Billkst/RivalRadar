from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-version.py"


def _write_project(root: Path, *, version: str) -> None:
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "scripts" / SCRIPT.name)

    (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"## [{version}]\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"Version history, latest v{version}\n"
        f"Current version: **v{version}**\n",
        encoding="utf-8",
    )
    (root / "README.zh-CN.md").write_text(
        f"版本历史,最新 v{version}\n"
        f"当前版本: **v{version}**\n",
        encoding="utf-8",
    )

    app_module = root / "rivalradar" / "api" / "app.py"
    app_module.parent.mkdir(parents=True)
    (root / "rivalradar" / "__init__.py").write_text("", encoding="utf-8")
    (root / "rivalradar" / "api" / "__init__.py").write_text("", encoding="utf-8")
    app_module.write_text(
        "from types import SimpleNamespace\n\n"
        "def create_app():\n"
        f'    return SimpleNamespace(version="{version}")\n',
        encoding="utf-8",
    )


def _run_check(root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    return subprocess.run(
        [sys.executable, "scripts/check-version.py"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_accepts_consistent_version_declarations(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write_project(root, version="1.2.3.4")

    result = _run_check(root)

    assert result.returncode == 0
    assert result.stdout == "version consistency: 1.2.3.4\n"
    assert result.stderr == ""


def test_cli_rejects_invalid_version_without_traceback(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write_project(root, version="1.2.3")

    result = _run_check(root)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "版本检查失败: VERSION 格式无效: '1.2.3'\n"


def test_cli_reports_missing_declaration_without_internal_pattern(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    _write_project(root, version="1.2.3.4")
    (root / "README.md").write_text(
        "Version history, latest v1.2.3.4\n",
        encoding="utf-8",
    )

    result = _run_check(root)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "版本检查失败: README.md 缺少版本声明\n"


def test_cli_reports_version_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write_project(root, version="1.2.3.4")
    (root / "CHANGELOG.md").write_text(
        "## [9.9.9.9]\n",
        encoding="utf-8",
    )

    result = _run_check(root)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        "版本不一致: VERSION=1.2.3.4\n"
        "- CHANGELOG.md latest release: 9.9.9.9\n"
    )
