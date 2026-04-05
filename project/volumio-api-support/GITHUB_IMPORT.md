# Import project backlog into GitHub (Project + Issues)

This repo now includes an automation script to create the GitHub Project and all backlog issues directly from local markdown files.

## Prerequisites

- Python 3
- A GitHub token with sufficient scopes:
  - classic token: `repo`, `project`
  - fine-grained token: repository issues write + organization/user projects write

## Command

```bash
GITHUB_TOKEN=YOUR_TOKEN \
python scripts/create_github_project_and_issues.py \
  --owner YOUR_ORG_OR_USER \
  --repo YOUR_REPO \
  --project-title "Volumio API Event Ingestion Migration" \
  --issues-dir project/volumio-api-support/issues
```

## Dry-run first

```bash
GITHUB_TOKEN=YOUR_TOKEN \
python scripts/create_github_project_and_issues.py \
  --owner YOUR_ORG_OR_USER \
  --repo YOUR_REPO \
  --project-title "Volumio API Event Ingestion Migration" \
  --dry-run
```

## What it does

1. Detects whether owner is user or organization.
2. Creates a new GitHub Project (v2).
3. Creates issues from all `ISSUE-*.md` files.
4. Adds created issues to the new project.

## Notes

- If label `volumio-migration` does not exist, GitHub may reject label assignment depending on repository settings. Re-run with `--label` values that exist, or create the label first.
- Re-running without cleanup will create duplicate issues/projects.
