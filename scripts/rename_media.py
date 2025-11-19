#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

VIDEO_EXTS = {".mkv", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts"}

CODEC_MAP = {
    "hevc": "x265",
    "h265": "x265",
    "h.265": "x265",
    "h264": "x264",
    "h.264": "x264",
    "avc1": "x264",
}

TOKEN_PATTERN = re.compile(r"\b(WEB|\d{3,4}p|x264|x265|DV|ATMOS)\b", re.IGNORECASE)
# If a source tag already exists, don't add WEB
SOURCE_TAG_PATTERN = re.compile(
    r"\b(HDTV|BluRay|Blu-ray|Bluray|WEB-DL|WEBDL|WEBRip|WEB)\b", re.IGNORECASE
)

# Debug printing helper
DEBUG = False


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

    @staticmethod
    def supports_color():
        """Check if terminal supports color."""
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    """Add color to text if terminal supports it."""
    if Colors.supports_color():
        return f"{color}{text}{Colors.RESET}"
    return text


def dprint(*args, **kwargs):
    if DEBUG:
        print(colorize("DEBUG:", Colors.CYAN), *args, **kwargs)


def run_ffprobe(path: Path) -> Optional[dict]:
    try:
        # Capture streams and format with side data and tags
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
        dprint("Running", " ".join(cmd))
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return json.loads(result.stdout.decode())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def nearest_resolution(height: Optional[int], allowed: List[int]) -> Optional[int]:
    if not height:
        return None
    # Find nearest upper resolution (or exact match)
    upper = [x for x in allowed if x >= height]
    if upper:
        return min(upper)
    # If no upper bound, return the highest available
    return max(allowed)


def detect_video_codec(stream: dict) -> Optional[str]:
    codec = (stream.get("codec_name") or "").lower()
    if not codec:
        return None
    return CODEC_MAP.get(codec, codec)


def has_dolby_vision(stream: dict) -> bool:
    # Check side_data_list for DOVI or Dolby Vision references
    for item in stream.get("side_data_list", []) or []:
        sdt = (item.get("side_data_type") or "").lower()
        if "dovi" in sdt or "dolby vision" in sdt:
            return True
    # Some files may expose DV info in tags
    tags = stream.get("tags") or {}
    for k, v in tags.items():
        s = f"{k} {v}".lower()
        if "dolby vision" in s or re.search(r"\b(dv)\b", s):
            return True
    # DV may also appear in profile field (rarely explicit)
    prof = (stream.get("profile") or "").lower()
    if "dolby" in prof and "vision" in prof:
        return True
    return False


def has_atmos(audio_stream: dict) -> bool:
    # Dolby Atmos usually shows as E-AC-3 JOC profile
    profile = (audio_stream.get("profile") or "").lower()
    if "joc" in profile:  # Joint Object Coding
        return True
    # Some tags or codec_long_name can contain Atmos
    for k in ("codec_long_name", "title"):
        val = (audio_stream.get(k) or "").lower()
        if "atmos" in val:
            return True
    tags = audio_stream.get("tags") or {}
    for k, v in tags.items():
        s = f"{k} {v}".lower()
        if "atmos" in s:
            return True
    return False


def extract_metadata(ff: dict) -> Tuple[Optional[int], Optional[str], bool, bool]:
    video = next(
        (s for s in ff.get("streams", []) if s.get("codec_type") == "video"), None
    )
    if not video:
        return None, None, False, False
    height = video.get("height")
    codec = detect_video_codec(video)
    dv = has_dolby_vision(video)

    atmos = False
    for s in ff.get("streams", []):
        if s.get("codec_type") == "audio" and has_atmos(s):
            atmos = True
            break

    return height, codec, dv, atmos


def extract_existing_resolution(filename: str) -> Optional[int]:
    """Extract resolution tag from filename if present (e.g., 720p, 1080p, 2160p)."""
    match = re.search(r"\b(\d{3,4})p\b", filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def build_new_name(
    base: str,
    web: bool,
    res: Optional[int],
    codec: Optional[str],
    dv: bool,
    atmos: bool,
    sep: str = ".",
) -> str:
    tokens = []
    # Only add WEB when no explicit source tag like HDTV/BluRay is present
    if web and not SOURCE_TAG_PATTERN.search(base or ""):
        tokens.append("WEBDL")
    if res:
        tokens.append(f"{res}p")
    if codec:
        # normalize case to lower for x264/x265 labels
        tokens.append(codec.lower())
    if dv:
        tokens.append("DV")
    if atmos:
        tokens.append("ATMOS")

    if not tokens:
        return base

    # Avoid duplicating existing tokens if present in base
    existing = set(m.group(0).upper() for m in TOKEN_PATTERN.finditer(base))
    deduped = [t for t in tokens if t.upper() not in existing]
    if not deduped:
        return base

    return f"{base}{sep}{sep.join(deduped)}"


def safe_rename(src: Path, dst: Path) -> Path:
    if src == dst or dst.exists():
        if src == dst:
            return dst
        # If target exists, append a numeric suffix
        stem, suffix = dst.stem, dst.suffix
        parent = dst.parent
        i = 1
        while True:
            candidate = parent / f"{stem}.{i}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1
    return dst


def process_file(
    path: Path, allowed_res: List[int], dry_run: bool, sep: str
) -> Optional[Tuple[Path, Path, bool]]:
    ff = run_ffprobe(path)
    if not ff:
        return None
    height, codec, dv, atmos = extract_metadata(ff)
    nearest = nearest_resolution(height, allowed_res) if height else None

    base = path.stem

    # Check for resolution mismatch
    existing_res = extract_existing_resolution(base)
    has_mismatch = False
    if existing_res and nearest and existing_res != nearest:
        has_mismatch = True
        warning = f"Resolution mismatch: filename has {existing_res}p but video is {height}p (nearest: {nearest}p)"
        print(
            colorize(f"WARNING [{path.name}]: {warning}", Colors.YELLOW + Colors.BOLD)
        )

    new_base = build_new_name(
        base, web=True, res=nearest, codec=codec, dv=dv, atmos=atmos, sep=sep
    )
    dprint(
        f"{path.name}: height={height} nearest={nearest} codec={codec} dv={dv} atmos={atmos} => new='{new_base}'"
    )
    if new_base == base:
        return None
    new_path = path.with_name(new_base + path.suffix)
    new_path = safe_rename(path, new_path)
    if not dry_run:
        path.rename(new_path)
    return (path, new_path, has_mismatch)


def find_media_files(root: Path, recursive: bool) -> List[Path]:
    files: List[Path] = []
    if root.is_file():
        if root.suffix.lower() in VIDEO_EXTS:
            files.append(root)
        return files

    it = root.rglob("*") if recursive else root.glob("*")
    for p in it:
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            # Skip obvious samples
            if re.search(r"sample", p.name, re.IGNORECASE):
                continue
            files.append(p)
    return files


def main():
    parser = argparse.ArgumentParser(
        description="Rename media files to include WEB, resolution, codec, DV, ATMOS tags."
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to process")
    parser.add_argument(
        "--apply", action="store_true", help="Apply changes (default is dry-run)"
    )
    parser.add_argument(
        "--sep", default=".", help="Separator between added tags (default: '.')"
    )
    parser.add_argument(
        "--resolutions",
        default="720,1080,2160",
        help="Comma-separated list of allowed vertical resolutions for nearest mapping (default: 720,1080,2160)",
    )
    parser.add_argument(
        "--recursive", action="store_true", help="Recurse into directories"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable verbose debug output"
    )

    args = parser.parse_args()

    # Check ffprobe availability
    if not shutil.which("ffprobe"):
        print("Error: ffprobe not found in PATH. Please install ffmpeg.")
        raise SystemExit(2)

    global DEBUG
    DEBUG = args.debug

    allowed_res = []
    try:
        allowed_res = [int(x.strip()) for x in args.resolutions.split(",") if x.strip()]
    except ValueError:
        print(
            "Error: --resolutions must be a comma-separated list of integers, e.g., 720,1080,2160"
        )
        raise SystemExit(2)

    changes: List[Tuple[Path, Path, bool]] = []

    for p in args.paths:
        root = Path(p)
        if not root.exists():
            print(f"Warning: {root} does not exist, skipping")
            continue
        for f in find_media_files(root, recursive=args.recursive):
            res = process_file(f, allowed_res, dry_run=not args.apply, sep=args.sep)
            if res:
                changes.append(res)
                src, dst, has_mismatch = res
                action = (
                    colorize("RENAME", Colors.GREEN)
                    if args.apply
                    else colorize("DRY-RUN", Colors.BLUE)
                )

                # Highlight the differences between src and dst
                src_name = src.name
                dst_name = dst.name

                # Extract only the changed part (stem)
                src_stem = src.stem
                dst_stem = dst.stem

                if src_stem != dst_stem:
                    # Show what's being added/changed - highlight only the added tokens
                    # Find the difference: what was added to the name
                    if dst_stem.startswith(src_stem):
                        # Tokens were appended
                        added_part = dst_stem[len(src_stem) :]
                        display_dst = f"{src_stem}{colorize(added_part, Colors.GREEN + Colors.BOLD)}{dst.suffix}"
                    else:
                        # More complex change, just highlight the whole new name
                        display_dst = colorize(dst_name, Colors.GREEN + Colors.BOLD)

                    print(
                        f"{action}: {colorize(src_name, Colors.BOLD)} -> {display_dst}"
                    )
                else:
                    print(f"{action}: {src} -> {dst}")

    if not changes:
        print("No files needed renaming.")
    else:
        print(
            f"Done. {len(changes)} file(s) {'renamed' if args.apply else 'would be renamed'}."
        )


if __name__ == "__main__":
    main()
