---
name: deploy
description: Merge PR, verify CI, bump version, and publish to PyPI
allowed-tools: Bash, Read, Edit, Grep, Glob, WebFetch
---

# /deploy Skill

Deploy the current branch to PyPI after merging, CI verification, and version bump.

## Usage

```
/deploy              # auto-detect PR and version bump
/deploy patch        # force patch bump
/deploy minor        # force minor bump
/deploy major        # force major bump
```

## Workflow

### Step 1: Pre-flight Checks

1. Confirm we're on a feature branch (not main)
2. Find the open PR for this branch: `gh pr view --json number,title,state,mergeable`
3. If no PR exists, abort with message
4. Show the PR title and number, confirm with user before proceeding

### Step 2: Verify Documentation

Before merging, ensure `CLAUDE.md` is accurate and up to date:

1. **Test count** — run `grep -r "def test_" tests/ | wc -l` and compare to the count in CLAUDE.md. Update if stale.
2. **New modules** — check for any new `.py` files under `src/parlor/` not mentioned in the "Key Modules" section. Add them.
3. **New config fields** — check `config.py` dataclasses for fields not documented in the "Configuration" section. Add them.
4. **New agent events** — check `agent_loop.py` for any `AgentEvent(kind=...)` values not mentioned. Document them.
5. **Architecture changes** — if the PR added middleware, new routers, or changed the security model, update those sections.
6. **Version in pyproject.toml** — note the pre-bump version for reference.

If any updates are needed, commit them as part of the PR before merging:
```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for vX.Y.Z release"
git push
```

### Step 3: Merge PR

1. Merge the PR to main: `gh pr merge --squash --delete-branch`
2. Switch to main: `git checkout main && git pull`

### Step 4: Wait for CI

1. Get the latest commit SHA on main: `git rev-parse HEAD`
2. Poll CI status every 15 seconds, up to 10 minutes:
   ```
   gh run list --branch main --limit 1 --json status,conclusion,name,headSha
   ```
3. If CI fails, abort and show the failure URL:
   ```
   gh run list --branch main --limit 1 --json url,conclusion
   ```
4. If CI passes, continue

### Step 5: Determine Version Bump

Read `pyproject.toml` to get current version.

If the user passed a bump level (patch/minor/major), use that.

Otherwise, determine from the merged PR:
- Look at the PR title and commit messages on main since the last tag
- `feat:` or new files added -> **minor**
- `fix:`, `docs:`, `chore:`, `refactor:`, `test:` -> **patch**
- `BREAKING CHANGE` or `!:` in any commit -> **major**

Bump the version in `pyproject.toml` using semantic versioning.

### Step 6: Create Version Commit and Tag

```bash
git add pyproject.toml
git commit -m "chore: bump version to X.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

### Step 7: Build and Publish

1. Clean previous builds:
   ```bash
   rm -rf dist/ build/ *.egg-info src/*.egg-info
   ```
2. Build:
   ```bash
   python -m build
   ```
3. Check the build:
   ```bash
   twine check dist/*
   ```
4. Publish to PyPI:
   ```bash
   twine upload dist/*
   ```
   This uses credentials from `~/.pypirc` or `TWINE_USERNAME`/`TWINE_PASSWORD` env vars.

### Step 8: Verify

1. Wait 30 seconds for PyPI to index
2. Check the package is available:
   ```bash
   pip index versions parlor 2>/dev/null || pip install parlor== 2>&1 | head -5
   ```
3. Report success with the new version number and PyPI URL

## Error Handling

- If merge fails: show error, do not proceed
- If CI fails: show failure URL, do not proceed
- If build fails: show error, do not proceed
- If upload fails: the tag and version commit are already pushed; show error and suggest manual `twine upload dist/*`
- Never force-push or amend commits on main

## Output

On success:
```
Deployed parlor vX.Y.Z to PyPI
  PR: #NN (merged)
  CI: passed
  PyPI: https://pypi.org/project/parlor/X.Y.Z/
```
