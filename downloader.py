"""
downloader.py  —  Core download engine for YTmax
Uses yt-dlp to fetch streams and FFmpeg to merge video + audio.
"""
from __future__ import annotations

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
    quality: str = "4K"
    audio_only: bool = False
    subtitles: bool = True
    cookies_file: str = ""
    on_progress: Optional[Callable] = field(default=None, repr=False)
    on_complete: Optional[Callable] = field(default=None, repr=False)
    on_error:    Optional[Callable] = field(default=None, repr=False)


@dataclass
class PlaylistDownloadTask:
    playlist_url: str
    output_dir: Path
    quality: str = "4K"
    audio_only: bool = False
    subtitles: bool = True
    cookies_file: str = ""
    video_urls: list[str] = field(default_factory=list)
    on_progress: Optional[Callable] = field(default=None, repr=False)
    on_video_complete: Optional[Callable] = field(default=None, repr=False)
    on_complete: Optional[Callable] = field(default=None, repr=False)
    on_error: Optional[Callable] = field(default=None, repr=False)


@dataclass
class VideoInfo:
    title: str
    duration: int
    uploader: str
    thumbnail: str
    formats: list[dict]
    best_height: int
    thumbnails: list[str] = field(default_factory=list)


@dataclass
class PlaylistVideo:
    title: str
    url: str
    duration: int
    uploader: str
    thumbnail: str
    index: int


@dataclass
class PlaylistInfo:
    title: str
    uploader: str
    thumbnail: str
    video_count: int
    total_duration: int
    videos: list[PlaylistVideo]


# ─────────────────────────────────────────────
#  Quality → yt-dlp format string
# ─────────────────────────────────────────────

QUALITY_MAP: dict[str, str] = {
    "4K":    "bestvideo[height<=2160]+bestaudio/bestvideo+bestaudio/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best",
    "720p":  "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best",
    "best":  "bestvideo+bestaudio/best",
}


# ─────────────────────────────────────────────
#  Bot-check detection
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
#  URL detection
# ─────────────────────────────────────────────

_PLAYLIST_PATTERNS = (
    re.compile(r"youtube\.com/playlist\b", re.IGNORECASE),
    re.compile(r"[?&]list=[^&]+", re.IGNORECASE),
)


def is_playlist_url(url: str) -> bool:
    """Detect if a URL targets a YouTube playlist rather than a single video."""
    lower = url.lower()
    if "playlist?list=" in lower:
        return True
    if any(p.search(url) for p in _PLAYLIST_PATTERNS):
        return True
    return False


# ─────────────────────────────────────────────
#  Fetch video metadata
# ─────────────────────────────────────────────

def fetch_info(url: str, cookies_file: str = "") -> VideoInfo:
    import yt_dlp
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "js_runtimes": {"node": {}},
        "extractor_args": {"youtube": {"player_client": ["tv", "android", "ios", "web_creator"]}},
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", [])
    heights = [f.get("height") or 0 for f in formats if f.get("vcodec") != "none"]
    best_h = max(heights, default=0)

    return VideoInfo(
        title      = info.get("title", "Unknown"),
        duration   = info.get("duration", 0),
        uploader   = info.get("uploader", "Unknown"),
        thumbnail  = info.get("thumbnail", ""),
        thumbnails = [t.get("url") for t in info.get("thumbnails", []) if t.get("url")],
        formats    = formats,
        best_height = best_h,
    )


def fetch_playlist_info(url: str, cookies_file: str = "") -> PlaylistInfo:
    import yt_dlp

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "js_runtimes": {"node": {}},
        "extractor_args": {"youtube": {"player_client": ["tv", "android", "ios", "web_creator"]}},
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries", [])
    videos: list[PlaylistVideo] = []
    total_duration = 0

    for idx, entry in enumerate(entries):
        if not entry:
            continue
        dur = entry.get("duration") or 0
        videos.append(PlaylistVideo(
            title     = entry.get("title", "Unknown"),
            url       = entry.get("url", entry.get("webpage_url", "")),
            duration  = dur,
            uploader  = entry.get("uploader", entry.get("channel", "Unknown")),
            thumbnail = entry.get("thumbnail", ""),
            index     = idx + 1,
        ))
        total_duration += dur

    return PlaylistInfo(
        title          = info.get("title", "Unknown Playlist"),
        uploader       = info.get("uploader", info.get("channel", "Unknown")),
        thumbnail      = info.get("thumbnail", ""),
        video_count    = len(videos),
        total_duration = total_duration,
        videos         = videos,
    )


# ─────────────────────────────────────────────
#  Cookie validation
# ─────────────────────────────────────────────

_AUTH_COOKIES = frozenset({
    "SAPISID", "SID", "HSID", "SSID",
    "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO",
})


def validate_cookies(path: str) -> tuple[bool, str]:
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

    if not any("Netscape HTTP Cookie File" in ln for ln in lines[:5]):
        return False, (
            "Not a valid Netscape cookies.txt.\n"
            "  The file must start with: # Netscape HTTP Cookie File\n"
            "  Export it using the 'Get cookies.txt LOCALLY' browser extension."
        )

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
#  Download workers
# ─────────────────────────────────────────────

def download(task: DownloadTask) -> None:
    t = threading.Thread(target=_download_worker, args=(task,), daemon=True)
    t.start()


def download_playlist(task: PlaylistDownloadTask) -> None:
    t = threading.Thread(target=_download_playlist_worker, args=(task,), daemon=True)
    t.start()


def _download_playlist_worker(task: PlaylistDownloadTask) -> None:
    total = len(task.video_urls)
    if total == 0:
        if task.on_error:
            task.on_error("No video URLs to download.")
        return

    for idx, url in enumerate(task.video_urls):
        video_title = f"Video {idx + 1}"
        if task.on_progress:
            task.on_progress(idx, total, video_title, url)

        single = DownloadTask(
            url          = url,
            output_dir   = task.output_dir,
            quality      = task.quality,
            audio_only   = task.audio_only,
            subtitles    = task.subtitles,
            cookies_file = task.cookies_file,
            on_complete  = None,
            on_error     = None,
        )
        try:
            _download_worker(single)
            if task.on_video_complete:
                task.on_video_complete(idx + 1, total, video_title)
        except Exception as e:
            if task.on_error:
                task.on_error(f"Failed: {str(e)}")
            continue

    if task.on_complete:
        task.on_complete()


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

        def _hook(d: dict) -> None:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                done  = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0
                eta   = d.get("eta") or 0
                pct   = done / total * 100
                fname = Path(d.get("filename", "")).name
                if task.on_progress:
                    task.on_progress(pct, speed, eta, fname)
            elif d["status"] == "finished":
                if task.on_progress:
                    task.on_progress(100, 0, 0, Path(d.get("filename", "")).name)

        opts: dict = {
            "format":                       fmt,
            "outtmpl":                      str(task.output_dir / "%(title)s [%(height)sp].%(ext)s"),
            "merge_output_format":          "mp4",
            "progress_hooks":               [_hook],
            "quiet":                        True,
            "no_warnings":                  True,
            "js_runtimes":                  {"node": {}},
            "extractor_args":               {"youtube": {"player_client": ["tv", "android", "ios", "web_creator"]}},
            "postprocessors":               [{
                "key":             "FFmpegVideoConvertor",
                "preferedformat":  "mp4",
            }],
            "concurrent_fragment_downloads": 4,
        }

        if task.cookies_file:
            opts["cookiefile"] = task.cookies_file

        if task.audio_only:
            opts["postprocessors"] = [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "320",
            }]
            opts["outtmpl"] = str(task.output_dir / "%(title)s.%(ext)s")

        if task.subtitles and not task.audio_only:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = False
            opts["subtitleslangs"] = ["all"]
            opts.setdefault("postprocessors", []).append({
                "key":    "FFmpegSubtitlesConvertor",
                "format": "srt",
            })

        import yt_dlp
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([task.url])

        if task.on_complete:
            task.on_complete()

    except Exception as exc:
        raw = str(exc)
        if "Requested format is not available" in raw:
            msg = (
                "No video streams could be extracted for this video.\n"
                "  This is typically caused by YouTube forcing SABR streaming.\n"
                "  Ensure Node.js is installed or run:\n"
                "     pip install --upgrade yt-dlp yt-dlp-ejs"
            )
        elif is_age_error(raw):
            msg = (
                f"Age-restricted video.\n"
                f"  Load a cookies.txt from a logged-in Google account.\n"
                f"  Raw error: {raw}"
            )
        elif is_bot_error(raw):
            msg = (
                f"YouTube bot/sign-in check triggered.\n"
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
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 ** 2:
        return f"{bps/1024:.1f} KB/s"
    elif bps < 1024 ** 3:
        return f"{bps/1024**2:.1f} MB/s"
    return f"{bps/1024**3:.2f} GB/s"


def fmt_time(seconds: int) -> str:
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return ""
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)
