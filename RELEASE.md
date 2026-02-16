# Release Runbook

## Prerequisites

- PyPI project `tokvera` created.
- Repository secret `PYPI_API_TOKEN` set in GitHub Actions.
- Clean `main` branch with passing CI.

## Pre-release checklist

1. Confirm `pyproject.toml` version matches target release.
2. Run:
   - `python -m pip install -e .[dev]`
   - `python -m pytest`
3. Build locally:
   - `python -m pip install --upgrade build`
   - `python -m build`
4. Update `CHANGELOG.md` with release date and notes.

## Release steps

1. Commit release changes.
2. Create and push a version tag:
   - `git tag v0.1.0`
   - `git push origin v0.1.0`
3. Wait for `Publish` workflow to complete.
4. Verify package on PyPI.

## Rollback

- If publish fails before package release: fix and tag next patch version.
- If package is published with issues: ship a patch release (`0.1.1`).
