# Releasing pdf2csv

The `Release package` workflow in `.github/workflows/release.yml` builds and
smoke-tests distributions on pull requests and pushes to main. Publishing a
GitHub release additionally runs minimum/latest dependency checks and uploads
the checked artifacts to PyPI through Trusted Publishing. Pushing a tag alone
does not publish anything to PyPI.

## One-time publisher setup

An owner of the existing PyPI project must add a GitHub Trusted Publisher at:

<https://pypi.org/manage/project/pdf2csv/settings/publishing/>

Use these exact values:

| Field | Value |
| --- | --- |
| Owner | `ghodsizadeh` |
| Repository | `pdf2csv` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The workflow's publishing job uses the GitHub environment `pypi` and job-scoped
`id-token: write`. No PyPI API-token secret is required. Configure environment
reviewers in GitHub if you want a separate approval before uploads. Repository
Actions must be enabled and allow the PyPA publishing action.

PyPI's [Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
explains how to register the publisher. A successful build does not prove that
this account-level setup has been completed.

## Prepare a version

1. Create a release-preparation PR from main.
2. Set the same version in `pyproject.toml` and `pdf2csv/__init__.py`, then run
   `uv lock`. For example, use `0.3.0rc1` for the first release candidate and
   `0.3.0` for the eventual stable release.
3. Update `CHANGELOG.md` with changes and migration information.
4. Run the release checks locally and wait for all PR checks to pass:

   ```sh
   uv run --locked python scripts/check_release.py
   uv run --locked pytest -q
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked --group examples python examples/generate.py
   git diff --exit-code -- examples/
   uv build --no-sources --out-dir /tmp/pdf2csv-release-dist
   uvx twine check --strict /tmp/pdf2csv-release-dist/*
   ```

   Use an empty output directory so older distributions cannot be uploaded
   accidentally. CI builds in a fresh checkout, installs the wheel into a
   separate environment and runs `scripts/smoke_wheel.py` with isolated Python.
5. Merge the PR and wait for main's checks to pass.

## Publish the release candidate

Confirm the PyPI publisher above exists before publishing. From the repository:

```sh
git fetch origin main
git tag -a v0.3.0rc1 origin/main -m "pdf2csv 0.3.0rc1"
git push origin v0.3.0rc1
gh release create v0.3.0rc1 --verify-tag --prerelease \
  --title "pdf2csv 0.3.0rc1" --notes-file CHANGELOG.md
```

The tag must exactly match `v` plus the version in all three version sources.
The tagged commit must belong to main. Release candidates, alpha and beta
versions must have GitHub's prerelease flag; stable versions must not. The
workflow rejects mismatches before publishing, reruns the tests and dependency
matrix, checks the distribution metadata, and smoke-tests the installed wheel.

Follow the run and check the published installation in a fresh environment:

```sh
gh run list --workflow release.yml --event release
gh run watch <run-id> --exit-status
uv run --no-project --refresh-package pdf2csv --with pdf2csv==0.3.0rc1 \
  python -c "import pdf2csv; print(pdf2csv.__version__)"
uvx --from pdf2csv==0.3.0rc1 pdf2csv --help
```

The exact version opts into the candidate. Ordinary installations should remain
on the existing stable version until a stable release is published.

## Follow-up releases

Collect results from independent real-world PDFs. Fix candidate regressions
through PRs and release `0.3.0rc2`, etc. Once the scope is validated, prepare a
new PR for `0.3.0`, then tag and publish it without `--prerelease`. A stable
release still documents OCR, layout and bidirectional-text limitations.

If publishing fails, inspect the workflow before changing any tag. When no
files have reached PyPI, correct the publisher configuration and rerun the
failed publishing job using its existing checked artifacts. PyPI distributions
cannot be replaced with different contents under the same version; ship a new
version for code/artifact corrections. Do not move or reuse published tags.
