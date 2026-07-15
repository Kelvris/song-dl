<div align="center">

# 🎵 song-dl

### *Because paying for music is for people with jobs.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Platform: Linux / macOS / Windows](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-lightgrey)](.)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/p2CK5GUhZx)

---

**Download songs from YouTube & SoundCloud with rich metadata, cover art, and lyrics — all from your terminal.**

> I made this so I don't have to open 15 tabs to get a single song.  
> You're welcome. Or I'm sorry. Honestly both.

</div>

---

## ✨ What it does

- **Downloads audio** from YouTube, SoundCloud (via `yt-dlp`)
- **Auto-tags** your files with title, artist, album, year, genre — pulled from **iTunes** and **MusicBrainz**
- **Fetches lyrics** from **LRCLib** so you can pretend you know the words at karaoke
- **Embeds cover art** — because plain audio files are ugly
- **Works in your terminal** with an arrow-key navigable menu (yes, it's a TUI, not a GUI — we're terminal dwellers here)
- **Remembers everything** — SQLite download history so you can track your musical descent
- **Batch downloads** — throw a playlist at it, walk away, come back to a folder full of music

---

## 🚀 Quick Install

### One command. Go make coffee.

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Kelvris/song-dl/main/install.sh)
```

The installer will:
1. ✅ Check you have Python, pip, ffmpeg, and a JS runtime (Deno or Node)
2. ✅ Install missing system stuff (asks first — I'm not a monster)
3. ✅ Create an isolated venv at `~/.local/share/song-dl/` — your system Python stays untouched, I promise
4. ✅ Install `yt-dlp` and `mutagen`
5. ✅ Drop a `song-dl` command in `~/.local/bin/`

> **Windows users:** WSL works. Native Windows support is in my todo list, right after "touch grass" (currently #974).

### Update to the latest

```bash
song-dl --update
```

This replaces only the source files — your venv, pip packages, and config are left alone. Painless.

---

## 📖 Usage

### Just run it

```bash
song-dl
```

That's it. Arrow keys to navigate, Enter to select, Q to quit.  
It's like a menu from 1998, but for stealing music. Ethically. Probably.

### Basic workflow

```
1. Open song-dl
2. Search for a song (YouTube + SoundCloud)
3. Pick your result
4. Approve the metadata (or edit it — I won't judge)
5. Watch it download and tag itself
6. Repeat until your hard drive screams
```

---

## ⚙️ Settings

| Setting | What it does | Default |
|---------|-------------|---------|
| Format | `mp3`, `m4a`, `flac`, or `opus` | `mp3` |
| Quality | `0` (best) or a bitrate like `192k` | `0` |
| Output directory | Where your songs land | current folder |
| Search sources | YouTube, SoundCloud, or both | Both |
| Output pattern | How files are named | `{artist} - {title}` |
| Skip existing | Don't re-download | No |
| Cover art | Embed album art | Yes |
| Metadata lookup | Auto-fetch from iTunes/MusicBrainz | Yes |
| Debug logging | Write debug logs for troubleshooting | No |

All saved to `~/.config/song-dl/config.json`. You can edit it manually if you're brave.

---

## 🐛 Known issues

- Downloading too many songs at once may cause your inner hoarder to feel satisfied
- Terminal may glitch if you resize it mid-menu (we're working on it)
- The metadata isn't always perfect. iTunes and MusicBrainz don't agree on everything. Neither do my parents.
- If you find a bug, congrats — you're now a contributor. Open an issue.

---

## 📜 License

MIT. Do whatever you want. Sell it, fork it, put it on a USB stick and bury it in your backyard. I don't care.

Copyright (c) 2026 [MASUMxFROST](https://github.com/MASUMxFROST)

---

## 🙏 Acknowledgements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — The real MVP
- [mutagen](https://mutagen.readthedocs.io/) — Tagging wizard
- [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) — Apple, for once, did something useful
- [MusicBrainz](https://musicbrainz.org/) — The Wikipedia of music metadata
- [LRCLib](https://lrclib.net/) — For the lyrics I never remember

---

---

# 🧠 ADVANCED

This section is for people who want to know how the sausage is made. If you just want to download music, scroll back up. No hard feelings.

---

## 🏗️ Architecture

```
main.py → cli.py (argparse)
              │
              ├── interactive.py (TUI loop)
              │       │
              │       ├── tui.py (terminal rendering, input)
              │       ├── core.py (orchestrates download pipeline)
              │       │       ├── downloader.py (yt-dlp wrapper)
              │       │       ├── metadata.py (iTunes → MusicBrainz → LRCLib)
              │       │       └── tagger.py (mutagen wrapper)
              │       └── config.py (JSON config I/O)
              │
              └── core.py (CLI mode — single URLs, batch files)
```

Everything flows through `core.py`. It's the traffic cop. `tui.py` handles raw terminal bytes — ANSI codes, cursor positioning, keypress reading — so the rest of the code doesn't have to think about terminals.

---

## 🔄 Metadata resolution order

When a song is downloaded, metadata is fetched in this order, each step falling back to the next:

1. **iTunes Search API** — queried by artist + title. Returns album, year, genre, cover art URL, and a higher-confidence track name.
2. **MusicBrainz** — queried only if iTunes fails or returns partial data. Slower but more thorough.
3. **LRCLib** — queried for synced/timed lyrics. Simple REST call, no auth needed.
4. **yt-dlp info** — the download itself returns basic metadata (title, uploader, duration) as a fallback.

Cover art is downloaded separately and embedded directly into the audio file via mutagen. It is **not** saved as a separate file.

---

## 🧪 Running tests

Tests live in `tests/test_core.py` — no test framework, no dependencies. Self-contained `assert`-based runner:

```bash
# From the project root, using the venv's Python (needed for yt-dlp imports)
~/.local/share/song-dl/venv/bin/python3 tests/test_core.py

# Or if yt-dlp is installed system-wide
python3 tests/test_core.py
```

Currently **21 tests** covering:

| Module | What's tested |
|--------|---------------|
| `core.py` | `_sanitize_path` — invalid chars, slashes, whitespace, empty, all-invalid |
| `core.py` | `_apply_pattern` — basic, album path, fallback defaults, track numbers |
| `core.py` | `_is_url` — https, http, no-scheme, non-URLs |
| `metadata.py` | `clean_youtube_title` — strips "(Official Video)", "(Lyrics)", pipes |
| `tagger.py` | `_detect_mime` — JPEG, PNG, WebP, fallback |

---

## 🐞 Debug mode

Enable in Settings or set `"debug": true` in `~/.config/song-dl/config.json`:

```json
{
  "format": "mp3",
  "debug": true
}
```

A timestamped log is written to `~/.config/song-dl/debug.log`. It captures:
- yt-dlp invocation params (format, quality, video ID)
- Download success/failure with raw exception text
- Temp file paths checked
- Per-URL result from `process_input()`

This is your first line of defense before opening an issue.

---

## 📁 Config reference

`~/.config/song-dl/config.json` is a plain JSON file. Here's the full schema:

```json
{
  "format": "mp3",          // "mp3" | "m4a" | "flac" | "opus"
  "quality": "0",           // "0" (best) or bitrate like "192k"
  "output_dir": "",         // absolute path, or "" for current dir
  "output_pattern": "{artist} - {title}",
  "skip_existing": false,
  "no_cover": false,
  "no_metadata": false,
  "sources": ["ytsearch", "scsearch"],
  "max_results": 5,
  "debug": false
}
```

Available pattern variables: `{artist}`, `{album}`, `{title}`, `{track}`, `{ext}`.  
Example: `"{artist}/{album}/{track}. {title}"` produces `Artist/Album/01. Song Title.mp3`.

---

## 🧩 yt-dlp integration

`downloader.py` configures yt-dlp with four different option profiles depending on the format:

| Format | yt-dlp options |
|--------|---------------|
| **mp3** | `bestaudio` → `ffmpeg` extract to mp3 |
| **m4a** | `m4a` bestaudio directly |
| **flac** / **opus** | native format with `--audio-format` |

All profiles use:
- `quiet: True` + `noprogress: True` — progress is rendered by the TUI's custom hook
- `playretries: 5` — retries on transient failures
- `extractor_args: {"youtube": {"player_client": ["web_creator", "android_creator"]}}` — bypasses YouTube bot detection
- `js_runtimes` — auto-detects Deno or Node.js for YouTube's JS challenges
- A custom `progress_hook` that feeds percentage + speed back to the TUI status line

---

## 📦 How the installer works

`install.sh` is a standalone POSIX-shell script. It does not depend on Python being installed beforehand.

1. **OS detection** — Linux (apt) or macOS (brew)
2. **Dependency check** — Python 3.8+, pip, venv, ffmpeg, JS runtime
3. **Venv setup** — creates `~/.local/share/song-dl/venv/`, upgrades pip
4. **Source copy** — downloads the repo tarball from GitHub `main`, extracts `songdl/`, `main.py`, `requirements.txt`
5. **Pip install** — `yt-dlp` + `mutagen` inside the venv
6. **Launcher** — writes `~/.local/bin/song-dl` (a thin shell wrapper that activates the venv)

The `--update` path skips steps 1-3 and 5-6 — only the source files are replaced in-place using atomic renames.

---

## 🌿 Branch structure

| Branch | Purpose |
|--------|---------|
| `main` | Stable. Tagged releases only. Installer pulls from here. |
| `dev` | Active development. May be slightly ahead of `main`. |

Feature branches are short-lived and merged into `dev` first.

---

## 🛠️ Building from source

```bash
git clone https://github.com/Kelvris/song-dl.git
cd song-dl
python3 -m venv .venv
source .venv/bin/activate
pip install yt-dlp mutagen
python3 -m songdl
```

No build step. No `setup.py`. No `pyproject.toml`. It's a flat package. Deal with it.

---

## 🤝 Contributing

1. Fork it
2. Branch off `dev`
3. Make your change
4. Run the tests (see above)
5. Open a PR to `dev`

Keep it simple. No abstract factories. No over-engineered patterns. This is a tool, not a thesis.

---

<div align="center">

**Made with ❤️, ☕, and questionable life choices**

*If you like this, star it. If you don't, well... I respect your wrong opinion.*

</div>
