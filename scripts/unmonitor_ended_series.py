#!/usr/bin/env python3

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


def _build_url(base_url: str, path: str, query: Optional[Dict[str, Any]] = None) -> str:
    base = base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base + path
    if query:
        qs = urllib.parse.urlencode(query)
        url = f"{url}?{qs}"
    return url


def _api_request(
    base_url: str,
    api_key: str,
    path: str,
    method: str = "GET",
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Any:
    url = _build_url(base_url, path, query)
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, headers=headers, method=method, data=data)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 204:  # No content
                return None
            resp_data = resp.read()
            if not resp_data:
                return None
            return json.loads(resp_data.decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP error {e.code} for {url}: {e.reason}\n")
        raise
    except urllib.error.URLError as e:
        sys.stderr.write(f"Connection error for {url}: {e.reason}\n")
        raise


def _parse_env_file(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                env[key] = value
    except FileNotFoundError:
        pass
    return env


def _load_env_defaults() -> None:
    """Load .env files and set defaults into os.environ without overriding.

    Search order:
    1) Current working directory /.env
    2) Script directory /.env
    """
    paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]
    for p in paths:
        parsed = _parse_env_file(p)
        for k, v in parsed.items():
            os.environ.setdefault(k, v)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    val = val.strip().lower()
    return val in {"1", "true", "yes", "on"}


def _has_monitored_content(series: Dict[str, Any]) -> bool:
    """Check if a series has any monitored seasons or episodes."""
    seasons = series.get("seasons") or []

    for season in seasons:
        if season.get("monitored", False):
            return True

    # Also check statistics for monitored episode count if available
    stats = series.get("statistics") or {}
    monitored_count = stats.get("episodeCount", 0) or 0
    if monitored_count > 0:
        # This is total episode count, not monitored count
        # We need to rely on seasons monitored status
        pass

    return False


def unmonitor_ended_series(base_url: str, api_key: str, dry_run: bool = True) -> None:
    print(
        f"=== Sonarr: checking ended series with no monitored content (dry_run={dry_run}) ==="
    )

    series_list: List[Dict[str, Any]] = (
        _api_request(base_url, api_key, "/api/v3/series") or []
    )

    candidates: List[Dict[str, Any]] = []

    for s in series_list:
        # Skip if already unmonitored
        if not s.get("monitored", False):
            continue

        # Check if series is ended
        status = s.get("status", "").lower()
        if status != "ended":
            continue

        # Check if it has any monitored seasons/episodes
        if _has_monitored_content(s):
            continue

        candidates.append(s)

    if not candidates:
        print("Sonarr: no matching ended series found.")
        return

    print(f"Sonarr: found {len(candidates)} ended series with no monitored content.")

    for s in candidates:
        series_id = s.get("id")
        title = s.get("title") or "<unknown>"
        year = s.get("year") or "?"
        path = s.get("path") or "<no path>"
        status = s.get("status") or "unknown"

        seasons = s.get("seasons") or []
        season_info = f"{len(seasons)} season(s)"

        print(
            f" - Series #{series_id}: {title} ({year}) | {status} | {season_info} | {path}"
        )

        if not dry_run and series_id is not None:
            # Update the series to set monitored=false
            series_update = s.copy()
            series_update["monitored"] = False

            try:
                _api_request(
                    base_url,
                    api_key,
                    f"/api/v3/series/{series_id}",
                    method="PUT",
                    body=series_update,
                )
            except Exception as e:
                sys.stderr.write(f"Failed to unmonitor series #{series_id}: {e}\n")

    if dry_run:
        print("Sonarr: dry-run only; no series were unmonitored.")
    else:
        print("Sonarr: unmonitoring completed.")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Unmonitor ended Sonarr series that have no monitored seasons or episodes. "
            "Can be configured via environment variables and .env file."
        )
    )

    parser.add_argument(
        "--sonarr-url",
        default=os.getenv("SONARR_URL"),
        help="Base URL for Sonarr, e.g. http://localhost:8989 (env: SONARR_URL)",
    )
    parser.add_argument(
        "--sonarr-api-key",
        default=os.getenv("SONARR_API_KEY"),
        help="API key for Sonarr (env: SONARR_API_KEY)",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        default=_env_bool("APPLY", False),
        help=(
            "Actually unmonitor series. Without this flag the script runs in dry-run "
            "mode and only prints what would be unmonitored. (env: APPLY)"
        ),
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    _load_env_defaults()
    args = parse_args(argv)

    if not args.sonarr_url or not args.sonarr_api_key:
        print("Error: Sonarr URL and API key are required.")
        print(
            "Provide via --sonarr-url/--sonarr-api-key or SONARR_URL/SONARR_API_KEY env vars."
        )
        return 1

    dry_run = not args.apply

    try:
        unmonitor_ended_series(args.sonarr_url, args.sonarr_api_key, dry_run=dry_run)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
