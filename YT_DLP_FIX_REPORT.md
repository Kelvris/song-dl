# yt-dlp Download and Update Fix Report

Date: 2026-08-16  
Project: `song-dl`  
Current song-dl version: `0.4.3`

## Summary

Song downloads had started failing again with YouTube returning HTTP 403 errors. The
Settings update flow also checked only for a new `song-dl` release and did not check
the installed `yt-dlp` version.

The fix moves the project from stable-only `yt-dlp` tracking to the recommended
nightly channel, installs the dependencies required for full YouTube support, enables
the JavaScript runtime actually present on the system, and adds `yt-dlp` checking and
updating to Settings.

## Confirmed Failure

The debug log contained this failure for video `YEVcnTIq1us`:

```text
ERROR: unable to download video data: HTTP Error 403: Forbidden
```

At the time of diagnosis, the song-dl virtual environment contained:

```text
yt-dlp:     2026.07.04
yt-dlp-ejs: not installed
Deno:      not installed
Node.js:   v24.19.0
```

`2026.07.04` was still the latest stable `yt-dlp` release. That explains why the old
PyPI-based update check did not offer an update even though newer nightly builds and
YouTube fixes were available.

## Root Causes

### 1. The update checker only tracked stable releases

`check_ytdlp_update()` queried the main PyPI project metadata. Its `info.version`
field points to the latest stable release, so it could not detect newer nightly
builds.

This matters because yt-dlp warns that stable builds can become stale when supported
sites change, and recommends nightly builds for regular users and when diagnosing
site breakages.

### 2. Settings did not check yt-dlp

The Settings screen called only `songdl.core.check_for_update()`, which checks the
`song-dl` version on GitHub. The separate yt-dlp check existed only in the CLI startup
path.

### 3. Node.js was detected but never enabled

The installer detected Node.js and told the user yt-dlp would use it. However, the
downloader had removed its `js_runtimes` configuration.

yt-dlp enables Deno by default, but Node.js, Bun, and QuickJS must be enabled
explicitly. As a result, the installed Node.js runtime was not being used for
YouTube JavaScript challenges.

### 4. Full YouTube support dependencies were missing

The project installed bare `yt-dlp`, not `yt-dlp[default]`. The installed environment
therefore did not contain `yt-dlp-ejs`, which current yt-dlp documentation describes
as required for full YouTube support.

### 5. The updater reported success without checking pip

The old CLI updater ignored the return code from `pip install` and always printed a
success message. A failed update could therefore look successful.

## Code Changes

### `songdl/downloader.py`

- Added explicit JavaScript runtime discovery in this priority order:

  1. Deno
  2. Node.js
  3. Bun
  4. QuickJS

- The first available runtime is passed to yt-dlp using the Python `js_runtimes`
  option and its resolved executable path.
- Replaced the stable PyPI update query with the latest release query for
  `yt-dlp/yt-dlp-nightly-builds`.
- Added version normalization that correctly compares:

  - Stable versions such as `2026.07.04`
  - Nightly release tags such as `2026.08.16.020253`
  - PyPI development versions such as `2026.8.16.20253.dev0`

- Added `ytdlp_update_available(current, latest)` so CLI and Settings use the same
  comparison logic.
- Added `update_ytdlp()`, which runs the equivalent of:

```bash
python -m pip install --upgrade --pre "yt-dlp[default]"
```

- The update function has a five-minute timeout and returns the real pip error when
  installation fails.

### `songdl/cli.py`

- Reused the shared yt-dlp version comparison instead of maintaining a second parser.
- Changed update messaging to identify the target as a nightly build.
- Replaced the bare stable update with `update_ytdlp()`.
- Success is printed only if pip exits successfully.
- Pip failures are now shown to the user.

### `songdl/interactive.py`

- Changed the Settings prompt from:

```text
Check for updates?
```

to:

```text
Check song-dl and yt-dlp for updates?
```

- Settings now checks `song-dl` and `yt-dlp` independently.
- The installed and latest nightly yt-dlp versions are displayed.
- When yt-dlp is outdated, Settings offers to install the nightly release and its
  YouTube support packages.
- Update success and failure are reported accurately.
- A current `song-dl` installation now displays its exact installed version.

### `requirements.txt`

Changed:

```text
yt-dlp>=2023.0.0
```

to:

```text
yt-dlp[default]>=2026.7.4
```

The `default` extra installs yt-dlp's recommended dependencies, including
`yt-dlp-ejs`.

### `install.sh`

- Added `--pre` to the requirements installation so fresh installations can select
  nightly yt-dlp releases.
- Updated installer messages to say that the nightly/default package is installed.
- Raised the required Python version from 3.8 to 3.10 because current yt-dlp supports
  CPython 3.10 and newer.
- Updated every related dependency check and error message to use Python 3.10.

### `README.md`

- Updated the Python badge and documentation from Python 3.8+ to Python 3.10+.
- Documented nightly yt-dlp installation and recommended YouTube dependencies.
- Corrected the JavaScript runtime documentation to include Deno, Node.js, Bun, and
  QuickJS.
- Removed outdated claims about downloader options that were no longer in the code.
- Updated the manual source-install command to:

```bash
pip install --pre "yt-dlp[default]" mutagen
```

### `tests/test_downloader.py`

Added tests covering:

- Stable-to-nightly version comparison.
- Equivalent GitHub nightly and PyPI `.dev0` version handling.
- Reading the latest nightly release tag from the update response.
- Explicit Node.js selection when Deno is unavailable.
- Use of `--pre` and `yt-dlp[default]` in the updater.
- Proper reporting of pip update failures.

## Local Runtime Upgrade

For end-to-end verification, the existing song-dl virtual environment at
`~/.local/share/song-dl/venv` was upgraded from stable yt-dlp to:

```text
yt-dlp:     2026.08.16.020253
yt-dlp-ejs: 0.8.0
```

The default extra also installed or updated its recommended Python dependencies,
including Brotli, Certifi, PyCryptodomeX, Requests, urllib3, and WebSockets.

The dependency upgrade affected only song-dl's isolated virtual environment, not the
system Python installation.

## Verification Performed

### Automated checks

```text
Python compilation: passed
Repository tests:   26/26 passed
git diff --check:   passed
install.sh syntax:  passed
song-dl.sh syntax:  passed
```

The project does not currently include pytest in its virtual environment, so the test
functions were executed directly with the virtual environment's Python interpreter.

### Live update check

The patched checker successfully detected:

```text
Installed: 2026.07.04
Nightly:   2026.08.16.020253
Update:    available
```

### End-to-end download

The exact YouTube video that previously produced HTTP 403 was downloaded through the
project's `songdl.downloader.download_audio()` function and converted successfully:

```text
Video ID: YEVcnTIq1us
Result:   /tmp/songdl-verify.xPyqsO/YEVcnTIq1us.mp3
Status:   verified successfully
```

## Files Changed

```text
README.md
install.sh
requirements.txt
songdl/cli.py
songdl/downloader.py
songdl/interactive.py
tests/test_downloader.py
```

This report is stored in:

```text
YT_DLP_FIX_REPORT.md
```

## Important Deployment Notes

- The repository source changes are released in this commit as version `0.4.3`.
- The `song-dl` application version was bumped from `0.4.2` to `0.4.3` for this release.
- The installed virtual environment was upgraded, but the installed source copy at
  `~/.local/share/song-dl/songdl` was not overwritten with the repository changes.
- Therefore, the upgraded dependency fixes the runtime package, while the new Settings
  behavior becomes available after these source changes are installed or released.
- The successful download used the patched repository source through `PYTHONPATH=.`.

## Upstream References

- yt-dlp documentation and package page: <https://pypi.org/project/yt-dlp/>
- Latest yt-dlp nightly release: <https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest>
- yt-dlp repository: <https://github.com/yt-dlp/yt-dlp>
- yt-dlp EJS documentation: <https://github.com/yt-dlp/yt-dlp/wiki/EJS>

