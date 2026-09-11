#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(/usr/bin/mktemp -d /tmp/topsag-ssh-install.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP"
export TOPSAG_SSH_NONINTERACTIVE=1
export TOPSAG_SSH_BASE_URL="https://bastion.example.com"
export TOPSAG_SSH_USERNAME="alice"
export TOPSAG_SSH_HOST="web"
export TOPSAG_SSH_PREFIX="$TMP/share/topsag-ssh"
export TOPSAG_SSH_CONFIG_DIR="$TMP/config/topsag-ssh"
export TOPSAG_SSH_CONFIG="$TOPSAG_SSH_CONFIG_DIR/config.toml"
export TOPSAG_SSH_HOSTS_FILE="$TOPSAG_SSH_CONFIG_DIR/hosts"
export TOPSAG_SSH_ZSHRC="$TMP/.zshrc"
export TOPSAG_SSH_FORCE_WIZARD=1

mkdir -p "$HOME/Applications" "$HOME/Library/Application Support/iTerm2/DynamicProfiles"
/bin/zsh "$ROOT/install.sh"

grep -q 'base_url = "https://bastion.example.com"' "$TOPSAG_SSH_CONFIG"
grep -q 'name = "web"' "$TOPSAG_SSH_CONFIG"
grep -q '^web$' "$TOPSAG_SSH_HOSTS_FILE"
grep -q 'ssh-proxy.zsh' "$TOPSAG_SSH_ZSHRC"
[[ -d "$HOME/Applications/AgentJump.app" ]]
/usr/bin/plutil -p "$HOME/Applications/AgentJump.app/Contents/Info.plist" | grep -q agent
[[ -x "$TOPSAG_SSH_PREFIX/macos/agent_jump.py" ]]
[[ -f "$HOME/Library/Application Support/iTerm2/DynamicProfiles/topsag-ssh.json" ]]
if grep -q baoleiji "$TOPSAG_SSH_CONFIG"; then
    print -u2 "company URL leaked into config"
    exit 1
fi

/bin/zsh "$ROOT/uninstall.sh"
[[ ! -d "$TOPSAG_SSH_PREFIX" ]]
[[ -f "$TOPSAG_SSH_CONFIG" ]]
/bin/zsh "$ROOT/uninstall.sh" --purge
[[ ! -d "$TOPSAG_SSH_CONFIG_DIR" ]]

print "INSTALL_OK"
