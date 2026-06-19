<div align="center">

# 🎵 song-dl

**Download songs with rich metadata tagging — from your terminal.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Platform: Linux / macOS / Windows](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-lightgrey)](https://github.com/Kelvris/song-dl#-quick-install)

</div>

---

## ✨ Features

- **🎵 Download audio** from YouTube, SoundCloud, and other sites (via `yt-dlp`)
- **🏷️ Rich metadata tagging** — automatically fetches title, artist, album, year, genre, and cover art from **iTunes** and **MusicBrainz**
- **📝 Lyrics** — auto-fetches synced/plain lyrics from **LRCLib**
- **🎨 Beautiful TUI** — arrow-key navigable interactive menu with colors
- **📦 Batch & playlist support** — download entire playlists or lists from a file
- **⚡ Parallel downloads** — processes batch items concurrently (3 workers)
- **📋 Download history** — keeps a searchable record of everything you've downloaded
- **🎯 Custom output patterns** — organize your music your way (e.g., `{artist}/{album}/{title}`)
- **🖼️ Cover art** — embeds album artwork directly into audio files
- **🎚️ Multiple formats** — MP3, M4A (AAC), FLAC, Opus

---

## 🚀 Quick Install

### One-liner (Linux / macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/Kelvris/song-dl/main/install.sh | bash
```

### Manual

```bash
git clone https://github.com/Kelvris/song-dl.git
cd song-dl
chmod +x install.sh
./install.sh
```

The installer will:
1. ✅ Check your system for Python 3.8+, pip, and ffmpeg
2. ✅ Install any missing system dependencies (with your permission)
3. ✅ Create an isolated virtual environment (never touches system Python)
4. ✅ Install `yt-dlp` and `mutagen` Python packages
5. ✅ Set up the `song-dl` command in `~/.local/bin/`

> **Windows support coming soon.** For now, you can run it in WSL.

---

## 📖 Usage

### Interactive Mode (recommended)

```bash
song-dl
```

This opens the full TUI menu where you can search, browse, configure settings, and manage your queue — all with arrow keys.

### Command Line (coming soon)

```bash
song-dl --url "https://youtube.com/watch?v=..."
song-dl --batch playlist.txt
```

---

## 🎮 Interactive Menu Walkthrough

```
╔════════════════════════════════════════╗
║        song-dl  v0.2.0                ║
║   Download songs + rich metadata       ║
╚════════════════════════════════════════╝

  ▸ Search & Download   (pick sources)
    Download URL        (video / playlist)
    Batch download      (from file)
    Queue (empty)
    Download history
    Settings
    Exit
```

| Option | What it does |
|--------|-------------|
| **Search & Download** | Search YouTube / SoundCloud, pick results, add to queue |
| **Download URL** | Paste a video or playlist URL |
| **Batch download** | Load URLs from a text file |
| **Queue** | View, remove items, or process all downloads |
| **Download history** | Browse past downloads |
| **Settings** | Configure format, quality, output directory, patterns |

### Settings

Configure your defaults interactively:

```
Format (mp3/m4a/flac/opus)
Quality (0=best or 192k)
Output directory
Skip existing? (y/n)
Skip cover art? (y/n)
Skip metadata lookup? (y/n)
Output pattern  ({artist} - {title}, {artist}/{album}/{title}, etc.)
```

All settings persist in `~/.config/song-dl/config.json`.

---

## 💽 Supported Formats

| Format | Codec | Quality Range | Tagging Support |
|--------|-------|---------------|-----------------|
| `mp3`  | MP3   | 0 (best) – 320k | ID3 tags + cover art |
| `m4a`  | AAC   | 0 (best) – 320k | MP4 tags + cover art |
| `flac` | FLAC  | 0 (best)        | FLAC metadata + cover art |
| `opus` | Opus  | 0 (best)        | Ogg Opus tags + cover art |

---

## 🗂️ Project Structure

```
song-dl/
├── install.sh          # 🆕 One-command installer (Linux/macOS)
├── main.py             # Entry point
├── requirements.txt    # Python dependencies
├── songdl/
│   ├── __init__.py     # Version info
│   ├── cli.py          # CLI argument parser
│   ├── config.py       # Persistent config (JSON)
│   ├── core.py         # Core download & processing logic
│   ├── downloader.py   # yt-dlp wrapper
│   ├── history.py      # SQLite download history
│   ├── interactive.py  # TUI menu system
│   ├── metadata.py     # iTunes / MusicBrainz / LRCLib lookups
│   └── tagger.py       # Audio tagging (MP3, M4A, FLAC, Opus)
├── song-dl.sh          # Legacy launcher
├── audio-get.sh        # Legacy launcher
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🔧 Dependencies

| Dependency | Purpose |
|-----------|---------|
| **Python 3.8+** | Runtime |
| **yt-dlp** | Audio extraction from YouTube / SoundCloud |
| **mutagen** | Audio metadata tagging |
| **ffmpeg** | Audio format conversion (required by yt-dlp) |

The installer handles all of these automatically.

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙌 Acknowledgements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — The backbone of audio extraction
- [mutagen](https://mutagen.readthedocs.io/) — Audio tagging library
- [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) — Metadata source
- [MusicBrainz](https://musicbrainz.org/) — Metadata source
- [LRCLib](https://lrclib.net/) — Lyrics source

---

<div align="center">
  Made with ❤️ by <a href="https://github.com/MASUMxFROST">MASUMxFROST</a>
</div>
