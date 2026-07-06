<div align="center">

# 🎵 song-dl

### *Because paying for music is for people with jobs.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Platform: Linux / macOS / Windows](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-lightgrey)](.)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/p2CK5guHZx)

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

All saved to `~/.config/song-dl/config.json`. You can edit it manually if you're brave.

---

## 🗂️ Project structure

```
song-dl/
├── install.sh          # The magic one-command installer
├── main.py             # Entry point (just calls the CLI)
├── requirements.txt    # yt-dlp + mutagen = all you need
├── songdl/
│   ├── cli.py          # Argparse wrapper
│   ├── config.py       # JSON config reader/writer
│   ├── core.py         # The brain — orchestrates everything
│   ├── downloader.py   # Talks to yt-dlp so you don't have to
│   ├── history.py      # SQLite — remembers your bad decisions
│   ├── interactive.py  # The whole TUI (600 lines of pain)
│   ├── metadata.py     # iTunes + MusicBrainz + LRCLib
│   └── tagger.py       # Writes tags to mp3/m4a/flac/opus
├── LICENSE
└── README.md           # You are here. Hello.
```

---

## 🧩 Dependencies

| Thing | Why |
|-------|-----|
| **Python 3.8+** | The language I wrote this in. Yes, I know. |
| **yt-dlp** | The real hero. Does all the heavy lifting. |
| **mutagen** | Tags your files so they look legit in MusicBee |
| **ffmpeg** | Converts formats. Required by yt-dlp. |
| **Deno or Node.js** | yt-dlp needs a JS runtime for YouTube extraction now. Deno is lighter. |

The installer handles all of these. Except coffee. That's on you.

---

## 🐛 Known issues

- Downloading too many songs at once may cause your inner hoarder to feel satisfied
- Terminal may glitch if you resize it mid-menu (we're working on it — see issue #12)
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

<div align="center">

**Made with ❤️, ☕, and questionable life choices**

*If you like this, star it. If you don't, well... I respect your wrong opinion.*

</div>
