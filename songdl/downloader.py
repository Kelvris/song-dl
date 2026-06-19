import os
import yt_dlp


def get_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
        return ydl.extract_info(url, download=False)


def get_playlist_info(url, timeout=10):
    """Fast playlist extraction (flat format, with socket timeout)."""
    with yt_dlp.YoutubeDL({
        'quiet': True, 'no_warnings': True,
        'extract_flat': 'in_playlist',
        'socket_timeout': timeout,
    }) as ydl:
        return ydl.extract_info(url, download=False)


def search_source(prefix, query, max_results=5):
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
        return ydl.extract_info(f"{prefix}{max_results}:{query}", download=False)


def cleanup_temps(output_dir, video_id):
    """Remove any leftover temp/partial files for a given video_id."""
    if not video_id:
        return
    for ext in ('webm', 'm4a', 'mkv', '3gp', 'part', 'ytdl'):
        f = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


def download_audio(url, output_dir, format='mp3', quality='0'):
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info.get('id', '')

    opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format,
            'preferredquality': quality,
        }],
        'quiet': False,
        'no_warnings': False,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        cleanup_temps(output_dir, video_id)
        raise

    # Find actual output file (yt-dlp may fall back to different extension)
    expected = os.path.join(output_dir, f"{video_id}.{format}")
    if os.path.exists(expected):
        return expected, info
    for ext in ('m4a', 'opus', 'flac', 'mp3', 'wav', 'aac'):
        f = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(f):
            return f, info
    return expected, info
