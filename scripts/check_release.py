"""Check package versions and, on release events, the tag and prerelease flag."""

import ast
import json
import os
from pathlib import Path
import re
import tomllib


def check_release(root: Path, release: dict | None = None) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text())
    version = project["project"]["version"]
    match = re.fullmatch(r"\d+\.\d+\.\d+(?P<pre>(?:a|b|rc)\d+)?", version)
    if match is None:
        raise ValueError(f"Unsupported release version: {version}")
    module = ast.parse((root / "pdf2csv/__init__.py").read_text())
    versions = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
    ]
    if versions != [version]:
        raise ValueError("__version__ must match pyproject.toml")
    lock = tomllib.loads((root / "uv.lock").read_text())
    locked = [p["version"] for p in lock["package"] if p["name"] == "pdf2csv"]
    if locked != [version]:
        raise ValueError("uv.lock must match pyproject.toml")
    if release is not None:
        if release.get("tag_name") != f"v{version}":
            raise ValueError(f"Release tag must be v{version}")
        if release.get("prerelease") is not bool(match.group("pre")):
            raise ValueError("GitHub prerelease flag must match the package version")
        if release.get("draft") is not False:
            raise ValueError("Only a published release can be uploaded")
    return version


def main():
    root = Path(__file__).resolve().parents[1]
    release = None
    if os.environ.get("GITHUB_EVENT_NAME") == "release":
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        if event.get("action") != "published":
            raise ValueError("Only release publication may trigger publishing")
        release = event["release"]
    print(f"Release metadata verified: {check_release(root, release)}")


if __name__ == "__main__":
    main()
