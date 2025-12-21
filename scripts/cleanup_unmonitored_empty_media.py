#!/usr/bin/env python3

import argparse
import os
import json
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
) -> Any:
    url = _build_url(base_url, path, query)
    headers = {"X-Api-Key": api_key}
    req = urllib.request.Request(url, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 204:  # No content
                return None
            data = resp.read()
            if not data:
                return None
            return json.loads(data.decode("utf-8"))
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


def cleanup_sonarr(base_url: str, api_key: str, dry_run: bool = True) -> None:
    print(
        f"=== Sonarr: checking unmonitored series with no files (dry_run={dry_run}) ==="
    )
    series: List[Dict[str, Any]] = (
        _api_request(base_url, api_key, "/api/v3/series") or []
    )

    candidates: List[Dict[str, Any]] = []
    for s in series:
        monitored = s.get("monitored", True)
        if monitored:
            continue

        stats = s.get("statistics") or {}
        size_on_disk = stats.get("sizeOnDisk", 0) or 0
        episode_file_count = stats.get("episodeFileCount", 0) or 0

        if size_on_disk <= 0 or episode_file_count == 0:
            candidates.append(s)

    if not candidates:
        print("Sonarr: no matching series found.")
        return

    print(f"Sonarr: found {len(candidates)} unmonitored series with no files.")

    for s in candidates:
        series_id = s.get("id")
        title = s.get("title") or "<unknown>"
        path = s.get("path") or "<no path>"
        print(f" - Series #{series_id}: {title} | {path}")

        if not dry_run and series_id is not None:
            _api_request(
                base_url,
                api_key,
                f"/api/v3/series/{series_id}",
                method="DELETE",
                query={
                    "deleteFiles": "false",
                    "addImportListExclusion": "false",
                },
            )

    if dry_run:
        print("Sonarr: dry-run only; no series were removed.")
    else:
        print("Sonarr: removal completed.")


def cleanup_radarr(base_url: str, api_key: str, dry_run: bool = True) -> None:
    print(
        f"=== Radarr: checking unmonitored movies with no files (dry_run={dry_run}) ==="
    )
    movies: List[Dict[str, Any]] = (
        _api_request(base_url, api_key, "/api/v3/movie") or []
    )

    candidates: List[Dict[str, Any]] = []
    for m in movies:
        monitored = m.get("monitored", True)
        if monitored:
            continue

        has_file = m.get("hasFile", False)
        size_on_disk = m.get("sizeOnDisk", 0) or 0

        if (not has_file) or size_on_disk <= 0:
            candidates.append(m)

    if not candidates:
        print("Radarr: no matching movies found.")
        return

    print(f"Radarr: found {len(candidates)} unmonitored movies with no files.")

    for m in candidates:
        movie_id = m.get("id")
        title = m.get("title") or "<unknown>"
        year = m.get("year") or "?"
        path = m.get("path") or "<no path>"
        print(f" - Movie #{movie_id}: {title} ({year}) | {path}")

        if not dry_run and movie_id is not None:
            _api_request(
                base_url,
                api_key,
                f"/api/v3/movie/{movie_id}",
                method="DELETE",
                query={
                    "deleteFiles": "false",
                    "addImportExclusion": "false",
                },
            )

    if dry_run:
        print("Radarr: dry-run only; no movies were removed.")
    else:
        print("Radarr: removal completed.")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove unmonitored Sonarr/Radarr items that have no files on disk "
            "(sizeOnDisk == 0 or no files). "
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
        "--radarr-url",
        default=os.getenv("RADARR_URL"),
        help="Base URL for Radarr, e.g. http://localhost:7878 (env: RADARR_URL)",
    )
    parser.add_argument(
        "--radarr-api-key",
        default=os.getenv("RADARR_API_KEY"),
        help="API key for Radarr (env: RADARR_API_KEY)",
    )

    parser.add_argument(
        "--no-sonarr",
        action="store_true",
        default=_env_bool("NO_SONARR", False),
        help="Do not touch Sonarr even if credentials are provided.",
    )
    parser.add_argument(
        "--no-radarr",
        action="store_true",
        default=_env_bool("NO_RADARR", False),
        help="Do not touch Radarr even if credentials are provided.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        default=_env_bool("APPLY", False),
        help=(
            "Actually remove items. Without this flag the script runs in dry-run "
            "mode and only prints what would be deleted."
        ),
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    _load_env_defaults()
    args = parse_args(argv)
    dry_run = not args.apply

    if (not args.sonarr_url or not args.sonarr_api_key) and (
        not args.radarr_url or not args.radarr_api_key
    ):
        print("Nothing to do: provide at least Sonarr or Radarr URL and API key.")
        return 1

    if args.sonarr_url and args.sonarr_api_key and not args.no_sonarr:
        try:
            cleanup_sonarr(args.sonarr_url, args.sonarr_api_key, dry_run=dry_run)
        except Exception:
            # Errors are already printed inside _api_request
            pass

    if args.radarr_url and args.radarr_api_key and not args.no_radarr:
        try:
            cleanup_radarr(args.radarr_url, args.radarr_api_key, dry_run=dry_run)
        except Exception:
            # Errors are already printed inside _api_request
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
