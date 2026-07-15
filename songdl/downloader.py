import os
import sys
import yt_dlp
from .tui import _debug

_COOKIE_FILE = os.path.expanduser("~/.config/song-dl/cookies.txt")

# ponytail: yt-dlp 2026.07+ works with default settings on YouTube.
# No need for extractor_args or js_runtimes — defaults handle everything.
_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
}


def _base_opts():
    opts = dict(_BASE_OPTS)
    if os.path.isfile(_COOKIE_FILE):
        opts["cookiefile"] = _COOKIE_FILE
    return opts


def check_ytdlp_update():
    """Check if yt-dlp is outdated. Returns (current, latest, error)."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"User-Agent": "song-dl/update-check"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        latest = data["info"]["version"]
        current = yt_dlp.version.__version__
        return current, latest, None
    except Exception as e:
        return yt_dlp.version.__version__, None, str(e)


def get_video_info(url):
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:
        return ydl.extract_info(url, download=False)


def get_playlist_info(url, timeout=10):
    """Fast playlist extraction (flat format, with socket timeout)."""
    opts = {**_base_opts(), "extract_flat": "in_playlist", "socket_timeout": timeout}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def search_source(prefix, query, max_results=5):
    query = query.strip()[:200].replace("\x00", "")
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:
        return ydl.extract_info(f"{prefix}{max_results}:{query}", download=False)


def _progress_hook(d):
    """yt-dlp progress hook — prints a single-line progress bar."""
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        parts = ["  Downloading..."]
        if pct:
            parts.append(pct)
        if speed:
            parts.append(speed)
        if eta:
            parts.append(f"ETA {eta}")
        print("  ".join(parts), flush=True)


def cleanup_temps(output_dir, video_id):
    """Remove any leftover temp/partial files for a given video_id."""
    if not video_id:
        return
    for ext in ("webm", "m4a", "mkv", "3gp", "part", "ytdl"):
        f = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


def download_audio(url, output_dir, format="mp3", quality="0"):
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info.get("id", "")

    opts = {
        **_base_opts(),
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": format,
                "preferredquality": quality,
            }
        ],
        "progress_hooks": [_progress_hook],
    }

    _debug(f"download_audio: starting url={url} format={format} quality={quality}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        print()  # clear progress line
        _debug(f"download_audio: yt-dlp download succeeded for {video_id}")
    except Exception as e:
        _debug(f"download_audio: yt-dlp failed for {video_id}: {type(e).__name__}: {e}")
        cleanup_temps(output_dir, video_id)
        raise

    # Find actual output file (yt-dlp may fall back to different extension)
    expected = os.path.join(output_dir, f"{video_id}.{format}")
    if os.path.exists(expected):
        return expected, info
    for ext in ("m4a", "opus", "flac", "mp3", "wav", "aac"):
        f = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(f):
            return f, info
    return expected, info
