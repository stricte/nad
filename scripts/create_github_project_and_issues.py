#!/usr/bin/env python3
"""Create GitHub issues from local backlog files and add them into a new Project (v2).

Usage:
  GITHUB_TOKEN=... python scripts/create_github_project_and_issues.py \
    --owner <owner> --repo <repo> \
    --project-title "Volumio API Event Ingestion Migration" \
    --issues-dir project/volumio-api-support/issues

Notes:
- Requires a token with repo + project scopes.
- Works for both user and organization owners.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass
class IssueSpec:
    file_path: pathlib.Path
    title: str
    body: str


def _request(method: str, url: str, token: str, payload: Optional[dict] = None) -> Any:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "nad-volumio-import-script",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}\n{detail}") from exc


def github_rest(method: str, endpoint: str, token: str, payload: Optional[dict] = None) -> Any:
    return _request(method, f"{API_BASE}{endpoint}", token, payload)


def github_graphql(query: str, variables: Dict[str, Any], token: str) -> Any:
    response = _request(
        "POST",
        GRAPHQL_URL,
        token,
        {
            "query": query,
            "variables": variables,
        },
    )
    if "errors" in response and response["errors"]:
        raise RuntimeError(f"GraphQL error: {response['errors']}")
    return response["data"]


def parse_issue_file(path: pathlib.Path) -> IssueSpec:
    text = path.read_text(encoding="utf-8").strip()
    first_line = text.splitlines()[0] if text else ""
    match = re.match(r"^#\s*(.+?)\s*$", first_line)
    if not match:
        raise ValueError(f"Issue file missing markdown H1 title: {path}")

    title = match.group(1)
    body = text
    return IssueSpec(file_path=path, title=title, body=body)


def load_issue_specs(issues_dir: pathlib.Path) -> List[IssueSpec]:
    files = sorted(issues_dir.glob("ISSUE-*.md"))
    if not files:
        raise ValueError(f"No issue files found in {issues_dir}")
    return [parse_issue_file(path) for path in files]


def get_owner_id(owner: str, token: str) -> Tuple[str, str]:
    query = """
    query($login: String!) {
      organization(login: $login) { id login }
      user(login: $login) { id login }
    }
    """
    data = github_graphql(query, {"login": owner}, token)
    if data.get("organization"):
        return data["organization"]["id"], "organization"
    if data.get("user"):
        return data["user"]["id"], "user"
    raise RuntimeError(f"Owner '{owner}' not found as org or user")


def create_project_v2(owner_id: str, title: str, token: str) -> str:
    mutation = """
    mutation($ownerId: ID!, $title: String!) {
      createProjectV2(input: {ownerId: $ownerId, title: $title}) {
        projectV2 { id title url }
      }
    }
    """
    data = github_graphql(mutation, {"ownerId": owner_id, "title": title}, token)
    project = data["createProjectV2"]["projectV2"]
    print(f"Created project: {project['title']} -> {project['url']}")
    return project["id"]


def create_issue(owner: str, repo: str, title: str, body: str, labels: List[str], token: str) -> dict:
    payload = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    return github_rest("POST", f"/repos/{owner}/{repo}/issues", token, payload)


def get_issue_node_id(owner: str, repo: str, issue_number: int, token: str) -> str:
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        issue(number: $number) { id number url }
      }
    }
    """
    data = github_graphql(query, {"owner": owner, "repo": repo, "number": issue_number}, token)
    issue = data["repository"]["issue"]
    if not issue:
        raise RuntimeError(f"Issue #{issue_number} not found in {owner}/{repo}")
    return issue["id"]


def add_item_to_project(project_id: str, content_id: str, token: str) -> None:
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    github_graphql(mutation, {"projectId": project_id, "contentId": content_id}, token)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub owner (org or user)")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--project-title", required=True, help="New GitHub Project (v2) title")
    parser.add_argument(
        "--issues-dir",
        default="project/volumio-api-support/issues",
        help="Directory containing ISSUE-*.md files",
    )
    parser.add_argument("--label", action="append", default=["volumio-migration"], help="Issue label")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without calling GitHub")

    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    issues_dir = pathlib.Path(args.issues_dir)
    specs = load_issue_specs(issues_dir)
    print(f"Loaded {len(specs)} issue specs from {issues_dir}")

    if args.dry_run:
        print(f"[DRY-RUN] Would create project '{args.project_title}' for {args.owner}/{args.repo}")
        for spec in specs:
            print(f"[DRY-RUN] Would create issue: {spec.title} ({spec.file_path.name})")
        return 0

    if not token:
        print("Missing GITHUB_TOKEN or GH_TOKEN", file=sys.stderr)
        return 2

    owner_id, owner_type = get_owner_id(args.owner, token)
    print(f"Owner type detected: {owner_type}")

    project_id = create_project_v2(owner_id, args.project_title, token)

    created_numbers: List[int] = []
    for spec in specs:
        issue = create_issue(args.owner, args.repo, spec.title, spec.body, args.label, token)
        issue_number = issue["number"]
        issue_url = issue["html_url"]
        created_numbers.append(issue_number)
        print(f"Created issue #{issue_number}: {issue_url}")

        issue_node_id = get_issue_node_id(args.owner, args.repo, issue_number, token)
        add_item_to_project(project_id, issue_node_id, token)
        print(f"Added issue #{issue_number} to project")

    print(f"Done. Created {len(created_numbers)} issues and added all to project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
