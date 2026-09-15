#!/bin/zsh
set -euo pipefail

PREFIX="${TOPSAG_SSH_PREFIX:-$HOME/.local/share/topsag-ssh}"
CONFIG_DIR="${TOPSAG_SSH_CONFIG_DIR:-$HOME/.config/topsag-ssh}"
ZSHRC="${TOPSAG_SSH_ZSHRC:-$HOME/.zshrc}"
APP="$HOME/Applications/AgentJump.app"
ITERM_PROFILE="$HOME/Library/Application Support/iTerm2/DynamicProfiles/topsag-ssh.json"
PURGE="${1:-}"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

print "Removing $PREFIX"
rm -rf "$PREFIX"

if [[ -d "$APP" ]]; then
    print "Removing $APP"
    if [[ -x "$LSREGISTER" ]]; then
        "$LSREGISTER" -u "$APP" >/dev/null 2>&1 || true
    fi
    rm -rf "$APP"
fi

if [[ -f "$ITERM_PROFILE" ]]; then
    print "Removing $ITERM_PROFILE"
    rm -f "$ITERM_PROFILE"
fi

wrapper="${TOPSAG_SSH_LOCAL_BIN:-$HOME/.local/bin}/ssh"
if [[ -f "$wrapper" ]] && grep -q "PATH wrapper for topsag-ssh" "$wrapper"; then
    print "Removing $wrapper"
    rm -f "$wrapper"
fi

zshenv="${TOPSAG_SSH_ZSHENV:-$HOME/.zshenv}"
if [[ -f "$zshenv" ]]; then
    /usr/bin/python3 - "$zshenv" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
kept = []
skip = 0
for line in text.splitlines(True):
    if "topsag-ssh PATH" in line:
        skip = 1
        continue
    if skip:
        skip = 0
        continue
    kept.append(line)
path.write_text("".join(kept))
PY
fi

if [[ -f "$ZSHRC" ]]; then
    /usr/bin/python3 - "$ZSHRC" "$PREFIX/shell/ssh-proxy.zsh" <<'PY'
import pathlib, sys
zshrc = pathlib.Path(sys.argv[1])
needle = sys.argv[2]
text = zshrc.read_text()
kept = []
skip_blank = False
for line in text.splitlines(True):
    if "topsag-ssh" in line or needle in line:
        skip_blank = True
        continue
    if skip_blank and line.strip() == "":
        skip_blank = False
        continue
    skip_blank = False
    kept.append(line)
zshrc.write_text("".join(kept))
PY
    print "Removed source line from $ZSHRC"
fi

if [[ "$PURGE" == "--purge" ]]; then
    rm -rf "$CONFIG_DIR"
    print "Removed $CONFIG_DIR"
    print "Keychain items named topsag-ssh-* were left in place."
else
    print "Kept $CONFIG_DIR and Keychain items. Pass --purge to delete the config directory."
fi
