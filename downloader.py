"""
downloader.py  —  Core download engine for YT4K
Uses yt-dlp to fetch 4K streams and FFmpeg to merge video + audio.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# ─────────────────────────────────────────────
#  Data types
# ─────────────────────────────────────────────

@dataclass
class DownloadTask:
    url: str
    output_dir: Path
    quality: str = "4K"          # "4K" | "1440p" | "1080p" | "720p" | "best"
    audio_only: bool = False
    cookies_file: str = ""       # absolute path to a Netscape cookies.txt, or ""
    on_progress: Optional[Callable] = field(default=None, repr=False)
    on_complete: Optional[Callable] = field(default=None, repr=False)
    on_error:    Optional[Callable] = field(default=None, repr=False)


@dataclass
class VideoInfo:
    title: str
    duration: int         # seconds
    uploader: str
    thumbnail: str        # URL
    formats: list[dict]
    best_height: int
    thumbnails: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
#  Quality → yt-dlp format string
# ─────────────────────────────────────────────

QUALITY_MAP: dict[str, str] = {
    # Adding an intermediate fallback (/bestvideo+bestaudio) ensures we grab
    # separate streams if available before falling back to merged /best.
    "4K":    "bestvideo[height<=2160]+bestaudio/bestvideo+bestaudio/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best",
    "720p":  "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best",
    "best":  "bestvideo+bestaudio/best",
}


# ─────────────────────────────────────────────
#  Fetch video metadata (no download)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  Bot-check detection
# ─────────────────────────────────────────────

# Substrings that indicate YouTube's bot/sign-in challenge
_BOT_SIGNALS = (
    "sign in to confirm",
    "confirm you're not a bot",
    "bot detection",
    "please sign in",
    "not a robot",
    "login required",
)

_AGE_SIGNALS = (
    "age-restricted",
    "age restricted",
    "inappropriate for some users",
    "confirm your age",
)


def is_bot_error(msg: str) -> bool:
    lower = msg.lower()
    return any(s in lower for s in _BOT_SIGNALS)


def is_age_error(msg: str) -> bool:
    lower = msg.lower()
    return any(s in lower for s in _AGE_SIGNALS)


def fetch_info(url: str, cookies_file: str = "") -> VideoInfo:
    """
    Fetches comprehensive metadata for a given YouTube URL without actually downloading the video streams.
    
    This function utilizes the `yt_dlp` library configured mathematically to simulate the browser
    environment (`tv`, `android`, `ios`, `web_creator` clients) in order to bypass specific client 
    blocking restrictions often imposed by YouTube (e.g. SABR streaming formats). It extracts 
    resolutions, durations, thumbnails, and validates active format bitrates seamlessly.

    Args:
        url (str): Target YouTube video URL.
        cookies_file (str): Optional absolute path pointer to the 'youtube.txt' authentication cookie.
    
    Returns:
        VideoInfo: Formatted data class packed with all essential UI metadata rendering variables.
    """
    import yt_dlp
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "js_runtimes": {"node": {}},
    }
    opts["extractor_args"] = {"youtube": {"player_client": ["tv", "android", "ios", "web_creator"]}}
    if cookies_file:
        opts["cookiefile"] = cookies_file
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", [])
    heights = [f.get("height") or 0 for f in formats if f.get("vcodec") != "none"]
    best_h  = max(heights, default=0)

    return VideoInfo(
        title     = info.get("title", "Unknown"),
        duration  = info.get("duration", 0),
        uploader  = info.get("uploader", "Unknown"),
        thumbnail = info.get("thumbnail", ""),
        thumbnails = [t.get("url") for t in info.get("thumbnails", []) if t.get("url")],
        formats   = formats,
        best_height = best_h,
    )


# ─────────────────────────────────────────────
#  Cookie validation
# ─────────────────────────────────────────────

# Cookies that indicate a properly authenticated Google/YouTube session
_AUTH_COOKIES = frozenset({
    "SAPISID", "SID", "HSID", "SSID",
    "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO",
})


def validate_cookies(path: str) -> tuple[bool, str]:
    """
    Check a Netscape cookies.txt file for YouTube authentication.

    Returns:
        (True, success_message)   — file looks good
        (False, error_message)    — something is wrong
    """
    p = Path(path)

    if not p.exists():
        return False, "File not found."
    if not p.is_file():
        return False, "Path is not a regular file."
    if p.stat().st_size == 0:
        return False, "File is empty."

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return False, f"Cannot read file: {exc}"

    lines = text.splitlines()

    # Must have the Netscape header
    if not any("Netscape HTTP Cookie File" in ln for ln in lines[:5]):
        return False, (
            "Not a valid Netscape cookies.txt.\n"
            "  The file must start with: # Netscape HTTP Cookie File\n"
            "  Export it using the 'Get cookies.txt LOCALLY' browser extension."
        )

    # Parse tab-separated cookie entries
    yt_cookies: dict[str, str] = {}
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split("\t")
        if len(parts) >= 7:
            domain, _, _path, _secure, _expires, name, value = parts[:7]
            if "youtube.com" in domain or "google.com" in domain:
                yt_cookies[name] = value

    if not yt_cookies:
        return False, (
            "No YouTube or Google cookies found in this file.\n"
            "  Make sure you exported cookies while on youtube.com and logged in."
        )

    found_auth = _AUTH_COOKIES & set(yt_cookies)
    if not found_auth:
        return False, (
            f"Found {len(yt_cookies)} YouTube cookies but none are authentication cookies.\n"
            "  You appear not to be logged in. Log into YouTube first, then re-export."
        )

    return True, (
        f"\u2714 Valid — {len(yt_cookies)} YouTube/Google cookies, "
        f"authenticated ({', '.join(sorted(found_auth))})."
    )


# ─────────────────────────────────────────────
#  Download (runs in background thread)
# ─────────────────────────────────────────────

def download(task: DownloadTask) -> None:
    """Starts the primary download methodology utilizing a fresh daemonized background thread to prevent UI freezing."""
    t = threading.Thread(target=_download_worker, args=(task,), daemon=True)
    t.start()


def _download_worker(task: DownloadTask) -> None:
    try:
        if task.audio_only:
            fmt = "bestaudio/best"
        elif task.quality in QUALITY_MAP:
            fmt = QUALITY_MAP[task.quality]
        elif task.quality.endswith("p") and task.quality[:-1].isdigit():
            h = task.quality[:-1]
            fmt = f"bestvideo[height<={h}]+bestaudio/bestvideo+bestaudio/best"
        else:
            fmt = QUALITY_MAP.get("4K")
            
        last_pct: list[float] = [0.0]

        def _hook(d: dict) -> None:
            if d["status"] == "downloading":
                total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                done    = d.get("downloaded_bytes", 0)
                speed   = d.get("speed") or 0
                eta     = d.get("eta") or 0
                pct     = done / total * 100
                fname   = Path(d.get("filename", "")).name
                last_pct[0] = pct
                if task.on_progress:
                    task.on_progress(pct, speed, eta, fname)
            elif d["status"] == "finished":
                if task.on_progress:
                    task.on_progress(100, 0, 0, Path(d.get("filename", "")).name)

        opts: dict = {
            "format":          fmt,
            "outtmpl":         str(task.output_dir / "%(title)s [%(height)sp].%(ext)s"),
            "merge_output_format": "mp4",
            "progress_hooks":  [_hook],
            "quiet":           True,
            "no_warnings":     True,
            "js_runtimes":     {"node": {}},
            # FFmpeg post-processor – merges video+audio
            "postprocessors":  [{
                "key":             "FFmpegVideoConvertor",
                "preferedformat":  "mp4",
            }],
            "concurrent_fragment_downloads": 4,
        }

        opts["extractor_args"] = {"youtube": {"player_client": ["tv", "android", "ios", "web_creator"]}}
        # Inject cookies file if provided
        if task.cookies_file:
            opts["cookiefile"] = task.cookies_file

        if task.audio_only:
            opts["postprocessors"] = [{
                "key":             "FFmpegExtractAudio",
                "preferredcodec":  "mp3",
                "preferredquality": "320",
            }]
            opts["outtmpl"] = str(task.output_dir / "%(title)s.%(ext)s")

        import yt_dlp
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([task.url])

        if task.on_complete:
            task.on_complete()

    except Exception as exc:  # noqa: BLE001
        raw = str(exc)
        # Check if the format is completely unavailable (usually meaning 0 formats extracted)
        if "Requested format is not available" in raw:
            msg = (
                "✖ No video streams could be extracted for this video.\n"
                "  This is typically caused by YouTube forcing SABR streaming for the web client.\n"
                "  If it still fails, ensure Node.js is installed or run:\n"
                "     pip install --upgrade yt-dlp yt-dlp-ejs"
            )
        # Always include the raw error so user (and we) can debug
        elif is_age_error(raw):
            msg = (
                f"⚠ Age-restricted video.\n"
                f"  Load a cookies.txt from a logged-in Google account.\n"
                f"  Raw error: {raw}"
            )
        elif is_bot_error(raw):
            msg = (
                f"⚠ YouTube bot/sign-in check triggered.\n"
                f"  Load a cookies.txt from your browser.\n"
                f"  Raw error: {raw}"
            )
        else:
            msg = raw
        if task.on_error:
            task.on_error(msg)


# ─────────────────────────────────────────────
#  Format helpers
# ─────────────────────────────────────────────

def fmt_size(bps: float) -> str:
    """Convert bytes/sec → human-readable string."""
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 ** 2:
        return f"{bps/1024:.1f} KB/s"
    elif bps < 1024 ** 3:
        return f"{bps/1024**2:.1f} MB/s"
    return f"{bps/1024**3:.2f} GB/s"


def fmt_time(seconds: int) -> str:
    """Convert seconds → mm:ss or hh:mm:ss."""
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def fmt_duration(seconds: int) -> str:
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)
