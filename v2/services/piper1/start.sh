#!/usr/bin/env bash
set -euo pipefail

VOICE="${PIPER_VOICE:-en_US-glados-medium}"
URI="${PIPER_URI:-tcp://0.0.0.0:10200}"
DATA_DIR="${PIPER_DATA_DIR:-/data}"
DOWNLOAD_DIR="${PIPER_DOWNLOAD_DIR:-$DATA_DIR}"

PIPER_RAW="${PIPER_BIN:-$(command -v piper || true)}"
if [[ -z "${PIPER_RAW}" ]]; then
  echo "ERROR: Unable to locate 'piper' executable. Install piper-tts or set PIPER_BIN." >&2
  exit 1
fi

read -r -a PIPER_CMD <<< "${PIPER_RAW}"
PIPER_PATH="${PIPER_CMD[0]}"
if [[ -z "${PIPER_PATH}" ]]; then
  echo "ERROR: PIPER_BIN resolved to an empty command." >&2
  exit 1
fi

PIPER_ARGS=("${PIPER_CMD[@]:1}")

if [[ -n "${PIPER_EXTRA_ARGS:-}" ]]; then
  read -r -a _EXTRA <<< "${PIPER_EXTRA_ARGS}"
  PIPER_ARGS+=("${_EXTRA[@]}")
fi

if [[ "${PIPER_USE_CUDA:-1}" != "0" ]]; then
  PIPER_ARGS+=("--cuda")
fi

PIPER_WRAPPER="$(mktemp /tmp/piper-XXXXXX.sh)"
{
  cat <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp)
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT
if "__PIPER_BIN__" __PIPER_ARGS__ "$@" 2>"$tmp"; then
  clean=$(sed -r 's/\x1B\[[0-9;]*[A-Za-z]//g' "$tmp")
  printf '%s\n' "$clean" >&2
  path=$(printf '%s\n' "$clean" | awk '/Wrote /{print $NF}' | tail -n1)
  if [ -n "$path" ]; then
    printf '%s\n' "$path"
  else
    exit 1
  fi
else
  cat "$tmp" >&2
  exit 1
fi
EOF
} > "${PIPER_WRAPPER}"

ARGS_ESC=""
if [[ ${#PIPER_ARGS[@]} -gt 0 ]]; then
  for arg in "${PIPER_ARGS[@]}"; do
    escaped="${arg//\"/\\\"}"
    ARGS_ESC+=" \"${escaped}\""
  done
fi

sed -i \
  -e "s|__PIPER_BIN__|${PIPER_PATH//\//\/}|" \
  -e "s|__PIPER_ARGS__|${ARGS_ESC}|" \
  "${PIPER_WRAPPER}"

chmod +x "${PIPER_WRAPPER}"
PIPER_EXEC="${PIPER_WRAPPER}"

ARGS=(python3 -m wyoming_piper --piper "${PIPER_EXEC}" --uri "${URI}" --voice "${VOICE}" --data-dir "${DATA_DIR}" --download-dir "${DOWNLOAD_DIR}")

if [[ "${PIPER_STREAMING:-1}" != "0" ]]; then
  ARGS+=(--streaming)
fi

if [[ -n "${PIPER_SPEAKER:-}" ]]; then
  ARGS+=(--speaker "${PIPER_SPEAKER}")
fi

if [[ -n "${PIPER_NOISE_SCALE:-}" ]]; then
  ARGS+=(--noise-scale "${PIPER_NOISE_SCALE}")
fi

if [[ -n "${PIPER_LENGTH_SCALE:-}" ]]; then
  ARGS+=(--length-scale "${PIPER_LENGTH_SCALE}")
fi

if [[ -n "${PIPER_NOISE_W_SCALE:-}" ]]; then
  ARGS+=(--noise-w "${PIPER_NOISE_W_SCALE}")
fi

if [[ -n "${PIPER_AUTO_PUNCTUATION:-}" ]]; then
  ARGS+=(--auto-punctuation "${PIPER_AUTO_PUNCTUATION}")
fi

if [[ -n "${PIPER_SAMPLES_PER_CHUNK:-}" ]]; then
  ARGS+=(--samples-per-chunk "${PIPER_SAMPLES_PER_CHUNK}")
fi

if [[ -n "${PIPER_MAX_PROCS:-}" ]]; then
  ARGS+=(--max-piper-procs "${PIPER_MAX_PROCS}")
fi

if [[ "${PIPER_UPDATE_VOICES:-0}" != "0" ]]; then
  ARGS+=(--update-voices)
fi

exec "${ARGS[@]}"
