#!/usr/bin/env python3
"""Check whether a newer context-cartographer skill version is available."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_REPO = "sergeylopukhov/context-cartographer"
DEFAULT_BRANCH = "main"
DEFAULT_PATH = "context-cartographer"
DEFAULT_INTERVAL_DAYS = 1
DEFAULT_TIMEOUT = 8
VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,3}(?:[-+][A-Za-z0-9_.-]+)?$")
REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "User-Agent": "context-cartographer-update-check",
}


class UpdateCheckError(RuntimeError):
    pass


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def read_local_version(base_dir: Path | None = None) -> str:
    version_path = (base_dir or skill_dir()) / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise UpdateCheckError(f"Local VERSION file not found: {version_path}") from exc
    if not version:
        raise UpdateCheckError(f"Local VERSION file is empty: {version_path}")
    return version


def raw_version_url(repo: str, branch: str, path: str) -> str:
    clean_path = path.strip("/")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{clean_path}/VERSION"


def fetch_remote_version(repo: str, branch: str, path: str, timeout: int) -> str:
    try:
        sha = fetch_branch_sha_from_git(repo, branch, timeout)
        return fetch_remote_version_from_raw(repo, sha, path, timeout, api_error="")
    except UpdateCheckError:
        pass
    try:
        return fetch_remote_version_from_api(repo, branch, path, timeout)
    except UpdateCheckError as exc:
        return fetch_remote_version_from_raw(repo, branch, path, timeout, api_error=str(exc))


def fetch_branch_sha_from_git(repo: str, branch: str, timeout: int) -> str:
    remote = f"https://github.com/{repo}.git"
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--heads", remote, branch],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateCheckError(f"Could not run git ls-remote: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise UpdateCheckError(f"git ls-remote failed: {detail}")
    first = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
    sha = first.split()[0] if first.split() else ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise UpdateCheckError("git ls-remote did not return a branch SHA.")
    return sha


def fetch_remote_version_from_raw(repo: str, branch: str, path: str, timeout: int, api_error: str) -> str:
    url = raw_version_url(repo, branch, path)
    try:
        request = Request(url, headers=REQUEST_HEADERS)
        with urlopen(request, timeout=timeout) as response:
            body = response.read(200).decode("utf-8", errors="replace")
    except URLError as exc:
        raise UpdateCheckError(f"Could not fetch remote VERSION from API or raw. API: {api_error}. Raw: {exc}") from exc
    version = body.strip().splitlines()[0] if body.strip() else ""
    if not version:
        raise UpdateCheckError(f"Remote VERSION is empty in API and raw responses. API: {api_error}. Raw: {url}")
    return version


def fetch_remote_version_from_api(repo: str, branch: str, path: str, timeout: int) -> str:
    clean_path = path.strip("/")
    url = f"https://api.github.com/repos/{repo}/contents/{clean_path}/VERSION?ref={branch}"
    try:
        request = Request(url, headers=REQUEST_HEADERS)
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except (URLError, json.JSONDecodeError) as exc:
        raise UpdateCheckError(f"Could not fetch remote VERSION from GitHub API: {exc}") from exc
    content = data.get("content")
    if not isinstance(content, str):
        raise UpdateCheckError("GitHub API response does not contain VERSION content.")
    try:
        body = base64.b64decode(content).decode("utf-8", errors="replace")
    except ValueError as exc:
        raise UpdateCheckError("Could not decode remote VERSION from GitHub API.") from exc
    version = body.strip().splitlines()[0] if body.strip() else ""
    if not version:
        raise UpdateCheckError("Remote VERSION is empty in GitHub API response.")
    return version


def version_key(version: str) -> tuple[tuple[int | str, ...], str]:
    if re.search(r"[-+]", version):
        main, sep, suffix = re.split(r"([-+])", version, maxsplit=1)
    else:
        main, sep, suffix = version, "", ""
    parts: list[int | str] = []
    for part in main.split("."):
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts), (sep + suffix)


def is_newer(remote: str, local: str) -> bool:
    if VERSION_RE.match(remote) and VERSION_RE.match(local):
        return version_key(remote) > version_key(local)
    return remote != local


def cache_path() -> Path:
    cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_home).expanduser() if cache_home else Path.home() / ".cache"
    return base / "context-cartographer" / "update-check.json"


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def should_check(cache: dict, interval_days: int, force: bool) -> bool:
    if force:
        return True
    checked_at = cache.get("checked_at")
    if not isinstance(checked_at, (int, float)):
        return True
    return (time.time() - float(checked_at)) >= interval_days * 86400


def build_result(
    *,
    checked: bool,
    update_available: bool,
    local_version: str,
    remote_version: str | None,
    message: str,
    install_commands: dict[str, str],
    error: str | None = None,
) -> dict:
    return {
        "checked": checked,
        "update_available": update_available,
        "local_version": local_version,
        "remote_version": remote_version,
        "message": message,
        "install_command": install_commands["codex"],
        "install_commands": install_commands,
        "error": error,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check for a newer context-cartographer version.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository, for example owner/repo.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Remote branch to check.")
    parser.add_argument("--path", default=DEFAULT_PATH, help="Skill folder path inside the repository.")
    parser.add_argument("--interval-days", type=int, default=DEFAULT_INTERVAL_DAYS, help="Minimum days between checks.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Network timeout in seconds.")
    parser.add_argument("--force", action="store_true", help="Ignore cache and check now.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    local_version = read_local_version()
    install_commands = {
        "codex": (
            "python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py "
            f"--repo {args.repo} --path {args.path}"
        ),
        "claude_code": (
            f"git clone https://github.com/{args.repo}.git /tmp/context-cartographer-update && "
            f"mkdir -p ~/.claude/skills && "
            f"rsync -a /tmp/context-cartographer-update/{args.path}/ ~/.claude/skills/context-cartographer/"
        ),
        "cursor_project": (
            "mkdir -p .cursor/skills && "
            f"rsync -a {args.path}/ .cursor/skills/context-cartographer/"
        ),
    }
    cache_file = cache_path()
    cache = load_cache(cache_file)

    if args.interval_days < 0:
        raise UpdateCheckError("--interval-days must be 0 or greater")

    if not should_check(cache, args.interval_days, args.force):
        remote_version = cache.get("remote_version") if isinstance(cache.get("remote_version"), str) else None
        update_available = bool(cache.get("update_available"))
        result = build_result(
            checked=False,
            update_available=update_available,
            local_version=local_version,
            remote_version=remote_version,
            message="Update check skipped because it was checked recently.",
            install_commands=install_commands,
        )
    else:
        try:
            remote_version = fetch_remote_version(args.repo, args.branch, args.path, args.timeout)
            update_available = is_newer(remote_version, local_version)
            message = (
                f"Update available: {local_version} -> {remote_version}."
                if update_available
                else f"context-cartographer is up to date: {local_version}."
            )
            result = build_result(
                checked=True,
                update_available=update_available,
                local_version=local_version,
                remote_version=remote_version,
                message=message,
                install_commands=install_commands,
            )
            save_cache(
                cache_file,
                {
                    "checked_at": time.time(),
                    "local_version": local_version,
                    "remote_version": remote_version,
                    "update_available": update_available,
                },
            )
        except UpdateCheckError as exc:
            result = build_result(
                checked=True,
                update_available=False,
                local_version=local_version,
                remote_version=None,
                message="Update check failed; continue without blocking the skill workflow.",
                install_commands=install_commands,
                error=str(exc),
            )

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["message"])
        if result["update_available"]:
            print("Ask the user before updating. Suggested command:")
            print(result["install_commands"]["codex"])
            print("For Claude Code or Cursor, use the matching install method from README.md.")
        if result["error"]:
            print(f"Reason: {result['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except UpdateCheckError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
