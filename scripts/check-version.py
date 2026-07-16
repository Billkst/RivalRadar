#!/usr/bin/env python3
"""Check that user-visible RivalRadar version declarations stay in sync."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VersionCheckError(ValueError):
    """Expected version declaration validation failure."""


def _read_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise VersionCheckError(f"VERSION 格式无效: {version!r}")
    return version


def _documented_versions(path: Path, patterns: tuple[str, ...]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    versions: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match is None:
            raise VersionCheckError(f"{path.relative_to(ROOT)} 缺少版本声明")
        versions.append(match.group("version"))
    return versions


def main() -> int:
    expected = _read_version()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    # Importing the app constructs no external clients and performs no network I/O.
    from rivalradar.api.app import create_app

    declared = {
        "pyproject.toml [project].version": pyproject["project"]["version"],
        "FastAPI OpenAPI version": create_app().version,
    }
    changelog_version = _documented_versions(
        ROOT / "CHANGELOG.md",
        (r"^## \[(?P<version>\d+\.\d+\.\d+\.\d+)\]",),
    )[0]
    declared["CHANGELOG.md latest release"] = changelog_version

    readme_patterns = (
        r"Version history, latest v(?P<version>\d+\.\d+\.\d+\.\d+)",
        r"Current version: \*\*v(?P<version>\d+\.\d+\.\d+\.\d+)\*\*",
    )
    readme_zh_patterns = (
        r"版本历史,最新 v(?P<version>\d+\.\d+\.\d+\.\d+)",
        r"当前版本: \*\*v(?P<version>\d+\.\d+\.\d+\.\d+)\*\*",
    )
    for index, version in enumerate(
        _documented_versions(ROOT / "README.md", readme_patterns), start=1
    ):
        declared[f"README.md version declaration {index}"] = version
    for index, version in enumerate(
        _documented_versions(ROOT / "README.zh-CN.md", readme_zh_patterns), start=1
    ):
        declared[f"README.zh-CN.md version declaration {index}"] = version

    mismatches = {
        label: version for label, version in declared.items() if version != expected
    }
    if mismatches:
        print(f"版本不一致: VERSION={expected}", file=sys.stderr)
        for label, version in mismatches.items():
            print(f"- {label}: {version}", file=sys.stderr)
        return 1

    print(f"version consistency: {expected}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except VersionCheckError as exc:
        print(f"版本检查失败: {exc}", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)
