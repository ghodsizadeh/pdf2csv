"""A release must identify the same version in every published entry point."""

from pathlib import Path

import pytest

from scripts.check_release import check_release


def make_project(root, version="0.3.0rc1"):
    (root / "pdf2csv").mkdir()
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
    (root / "pdf2csv/__init__.py").write_text(f'__version__ = "{version}"\n')
    (root / "uv.lock").write_text(
        f'[[package]]\nname = "pdf2csv"\nversion = "{version}"\n'
    )


def test_repository_versions_agree():
    assert check_release(Path(__file__).parents[1])


@pytest.mark.parametrize("version,prerelease", [("0.3.0rc1", True), ("0.3.0", False)])
def test_release_flags_agree_with_version(tmp_path, version, prerelease):
    make_project(tmp_path, version)
    event = {"tag_name": f"v{version}", "prerelease": prerelease, "draft": False}
    assert check_release(tmp_path, event) == version
    event["prerelease"] = not prerelease
    with pytest.raises(ValueError, match="prerelease flag"):
        check_release(tmp_path, event)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"tag_name": "v0.3.0"}, "Release tag"),
        ({"tag_name": "v0.3.0rc1; echo injected"}, "Release tag"),
        ({"draft": True}, "published release"),
        ({"prerelease": None}, "prerelease flag"),
    ],
)
def test_inconsistent_release_is_rejected(tmp_path, change, message):
    make_project(tmp_path)
    event = {"tag_name": "v0.3.0rc1", "prerelease": True, "draft": False}
    event.update(change)
    with pytest.raises(ValueError, match=message):
        check_release(tmp_path, event)


@pytest.mark.parametrize("filename", ["uv.lock", "pdf2csv/__init__.py"])
def test_stale_package_version_is_rejected(tmp_path, filename):
    make_project(tmp_path)
    path = tmp_path / filename
    path.write_text(path.read_text().replace("0.3.0rc1", "0.2.2"))
    with pytest.raises(ValueError, match="must match pyproject.toml"):
        check_release(tmp_path)
