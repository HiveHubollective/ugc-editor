#!/usr/bin/env bash
# One-time setup for the UGC editor. Safe to run again any time: it only
# installs what's missing, then checks everything works.
#
#   bash ~/.claude/skills/ugc-editor/scripts/setup.sh
#
# Installs: ffmpeg (cutting and rendering), uv (Python manager), and a private
# Python environment in ~/.ugc-editor with faster-whisper (ears), OpenCV and
# Pillow (eyes). Downloads the speech model (~460 MB) on first run.
set -uo pipefail
HOME_DIR="$HOME/.ugc-editor"
VENV="$HOME_DIR/venv"
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
ok()   { printf '  ✅ %s\n' "$1"; }
no()   { printf '  ❌ %s\n     %s\n' "$1" "$2"; FAIL=1; }
FAIL=0
echo "UGC editor setup"

OS="$(uname)"
if [ "$OS" = "Darwin" ]; then
  # Homebrew lives in /opt/homebrew on Apple Silicon and /usr/local on Intel Macs,
  # and isn't on the PATH of a fresh shell straight after it's installed.
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)" && break
  done
  if ! command -v brew >/dev/null; then
    echo "  Homebrew isn't installed. Install it first (it asks for your Mac password):"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
  fi
  command -v ffmpeg >/dev/null || brew install ffmpeg
  command -v uv >/dev/null || brew install uv
else
  command -v ffmpeg >/dev/null || { command -v apt-get >/dev/null && sudo apt-get install -y ffmpeg; }
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

command -v ffmpeg >/dev/null && ok "ffmpeg" || no "ffmpeg" "macOS: brew install ffmpeg"
command -v uv >/dev/null && ok "uv" || no "uv" "macOS: brew install uv"

mkdir -p "$HOME_DIR"
if [ ! -x "$VENV/bin/python" ]; then
  uv venv --python 3.12 "$VENV" >/dev/null 2>&1 || uv venv "$VENV"
fi
uv pip install --python "$VENV/bin/python" -q faster-whisper "opencv-python-headless<5" pillow numpy pillow-heif \
  && ok "Python tools (faster-whisper, OpenCV, Pillow)" || no "Python tools" "re-run this script; check your internet connection"

# Fonts for captions (libass reads them from the skill's fonts folder)
[ -s "$SKILL/fonts/Fredoka-Bold.ttf" ] && [ -s "$SKILL/fonts/Rubik-Black.ttf" ] && ok "caption fonts" \
  || no "caption fonts" "the fonts folder is missing - reinstall the skill"

# Ears: download the speech model once and prove it can hear
"$VENV/bin/python" - <<'PY' && ok "speech-to-text (ears)" || no "speech-to-text" "re-run; the first run downloads ~460 MB"
import subprocess, tempfile, os, numpy as np
from faster_whisper import WhisperModel
m = WhisperModel('small.en', device='cpu', compute_type='int8')
segs, _ = m.transcribe(np.zeros(16000, np.float32))
list(segs)
PY

# Eyes: face finding for smart zooms
"$VENV/bin/python" -c "import cv2; assert hasattr(cv2,'CascadeClassifier'); cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')" \
  && ok "face framing (eyes)" || no "face framing" "uv pip install --python $VENV/bin/python 'opencv-python-headless<5'"

FREE_GB=$(df -Pk "$HOME" | awk 'NR==2{print int($4/1048576)}')
[ "$FREE_GB" -ge 10 ] && ok "${FREE_GB} GB free disk" || no "only ${FREE_GB} GB free" "free up at least 10 GB"

if [ "$FAIL" = 0 ]; then
  echo "READY: say \"start a new UGC job\" to Claude."
  echo "Python for the scripts: $VENV/bin/python"
else
  echo "NOT READY: fix the ❌ items above, then run this again."; exit 1
fi
