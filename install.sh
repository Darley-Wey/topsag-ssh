#!/bin/zsh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${TOPSAG_SSH_PREFIX:-$HOME/.local/share/topsag-ssh}"
CONFIG_DIR="${TOPSAG_SSH_CONFIG_DIR:-$HOME/.config/topsag-ssh}"
CONFIG_FILE="${TOPSAG_SSH_CONFIG:-$CONFIG_DIR/config.toml}"
HOSTS_FILE="${TOPSAG_SSH_HOSTS_FILE:-$CONFIG_DIR/hosts}"
APP_DIR="$HOME/Applications"
APP="$APP_DIR/AgentJump.app"
PYTHON="${TOPSAG_SSH_PYTHON:-/usr/bin/python3}"
ZSHRC="${TOPSAG_SSH_ZSHRC:-$HOME/.zshrc}"
NONINTERACTIVE="${TOPSAG_SSH_NONINTERACTIVE:-}"
ITERM_PROFILE_DIR="$HOME/Library/Application Support/iTerm2/DynamicProfiles"
ITERM_PROFILE="$ITERM_PROFILE_DIR/topsag-ssh.json"
GUID="A8E2C1F0-4B77-4D3A-9E11-7C2F9B4D8A10"

export TOPSAG_SSH_PREFIX="$PREFIX"
export TOPSAG_SSH_CONFIG="$CONFIG_FILE"
export TOPSAG_SSH_HOSTS_FILE="$HOSTS_FILE"

prompt() {
    local message="$1"
    local default="${2:-}"
    local value=""
    if [[ -n "$NONINTERACTIVE" ]]; then
        print -r -- "$default"
        return
    fi
    if [[ -n "$default" ]]; then
        read "value?$message [$default]: "
        print -r -- "${value:-$default}"
    else
        read "value?$message: "
        print -r -- "$value"
    fi
}

yesno() {
    local message="$1"
    local default="${2:-n}"
    if [[ -n "$NONINTERACTIVE" ]]; then
        [[ "$default" == [yY]* ]]
        return $?
    fi
    local value
    read "value?$message [$default]: "
    value="${value:-$default}"
    [[ "$value" == [yY]* ]]
}

copy_tree() {
    mkdir -p "$PREFIX"
    /usr/bin/ditto "$REPO_ROOT/python" "$PREFIX/python"
    /usr/bin/ditto "$REPO_ROOT/macos" "$PREFIX/macos"
    /usr/bin/ditto "$REPO_ROOT/shell" "$PREFIX/shell"
    /usr/bin/ditto "$REPO_ROOT/share" "$PREFIX/share"
    chmod +x "$PREFIX/python/topsag_ssh.py" "$PREFIX/macos/agent_jump.py"
}

ensure_python_deps() {
    if ! "$PYTHON" -c 'import requests' >/dev/null 2>&1; then
        print "Installing requests for $PYTHON ..."
        "$PYTHON" -m pip install --user requests
    fi
    if ! "$PYTHON" -c 'import PIL' >/dev/null 2>&1; then
        print "Installing Pillow for local captcha OCR ..."
        "$PYTHON" -m pip install --user Pillow || print "Pillow install failed; captcha OCR will fall back to manual input."
    fi
}

write_config_wizard() {
    mkdir -p "$CONFIG_DIR"
    if [[ -f "$CONFIG_FILE" && -z "${TOPSAG_SSH_FORCE_WIZARD:-}" ]]; then
        print "Keeping existing $CONFIG_FILE"
        "$PYTHON" "$PREFIX/python/topsag_ssh.py" --write-hosts-file >/dev/null
        return
    fi
    local base_url username host_name insecure_value
    base_url="${TOPSAG_SSH_BASE_URL:-$(prompt "Bastion URL" "")}"
    username="${TOPSAG_SSH_USERNAME:-$(prompt "Username" "")}"
    host_name="${TOPSAG_SSH_HOST:-web}"
    if [[ -z "$NONINTERACTIVE" ]]; then
        host_name="$(prompt "SSH host name" "$host_name")"
    fi
    insecure_value="false"
    if [[ -n "${TOPSAG_SSH_INSECURE:-}" ]] || { [[ -z "$NONINTERACTIVE" ]] && yesno "Skip TLS verification" "n"; }; then
        insecure_value="true"
    fi
    if [[ -z "$base_url" || -z "$username" ]]; then
        print -u2 "base_url and username are required."
        exit 2
    fi
    cat > "$CONFIG_FILE" <<EOF
base_url = "$base_url"
username = "$username"
insecure = $insecure_value
language = "zh-cn"

[[hosts]]
name = "$host_name"
asset_index = 0
account_index = 0
protocol = "SSH"
EOF
    "$PYTHON" "$PREFIX/python/topsag_ssh.py" --write-hosts-file >/dev/null
    print "Wrote $CONFIG_FILE"
}

save_password() {
    if [[ -n "$NONINTERACTIVE" && -z "${TOPSAG_PASSWORD:-}" ]]; then
        print "Skipping Keychain password (TOPSAG_PASSWORD unset)."
        return
    fi
    "$PYTHON" "$PREFIX/python/topsag_ssh.py" --configure
}

install_agentjump() {
    mkdir -p "$APP_DIR"
    local script tmpdir plist lsregister
    tmpdir="$(/usr/bin/mktemp -d /tmp/topsag-agentjump.XXXXXX)"
    {
        script="$tmpdir/AgentJump.applescript"
        /usr/bin/sed "s|AGENT_JUMP_PY|$PREFIX/macos/agent_jump.py|g" \
            "$REPO_ROOT/macos/AgentJump.applescript" > "$script"
        /usr/bin/osacompile -o "$APP" "$script"
        plist="$APP/Contents/Info.plist"
        /usr/libexec/PlistBuddy -c 'Delete :CFBundleURLTypes' "$plist" >/dev/null 2>&1 || true
        /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes array' "$plist"
        /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0 dict' "$plist"
        /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLName string agent' "$plist"
        /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLSchemes array' "$plist"
        /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string agent' "$plist"
        if ! /usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.local.agentjump' "$plist" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string com.local.agentjump' "$plist"
        fi
        if ! /usr/libexec/PlistBuddy -c 'Set :CFBundleName AgentJump' "$plist" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c 'Add :CFBundleName string AgentJump' "$plist"
        fi
        /usr/bin/xattr -dr com.apple.quarantine "$APP" "$PREFIX" >/dev/null 2>&1 || true
        lsregister="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
        if [[ -x "$lsregister" ]]; then
            "$lsregister" -f "$APP" >/dev/null
        fi
        print "Installed $APP"
    } always {
        rm -rf "$tmpdir"
    }
}

install_zshrc() {
    local line="source \"$PREFIX/shell/ssh-proxy.zsh\""
    mkdir -p "$(dirname "$ZSHRC")"
    touch "$ZSHRC"
    if grep -F "$PREFIX/shell/ssh-proxy.zsh" "$ZSHRC" >/dev/null 2>&1; then
        print "zshrc already sources ssh-proxy.zsh"
        return
    fi
    print "\n# topsag-ssh\n$line" >> "$ZSHRC"
    print "Added source line to $ZSHRC"
}

install_iterm_profile() {
    local host_name
    host_name="$(awk -F '"' '/^name = / {print $2; exit}' "$CONFIG_FILE" 2>/dev/null || true)"
    host_name="${host_name:-web}"
    mkdir -p "$ITERM_PROFILE_DIR"
    if [[ -f "$ITERM_PROFILE" ]]; then
        print "Keeping existing iTerm profile $ITERM_PROFILE"
        return
    fi
    cat > "$ITERM_PROFILE" <<EOF
{
  "Profiles": [
    {
      "Name": "TopSAG SSH",
      "Guid": "$GUID",
      "Custom Command": "Yes",
      "Command": "/bin/zsh -lc 'source \"$PREFIX/shell/ssh-proxy.zsh\"; ssh $host_name'",
      "Badge Text": "TopSAG"
    }
  ]
}
EOF
    print "Wrote iTerm Dynamic Profile $ITERM_PROFILE"
}

print "Installing topsag-ssh into $PREFIX"
copy_tree
ensure_python_deps
write_config_wizard
save_password
install_agentjump
install_zshrc
install_iterm_profile
print
print "Done. Open a new terminal, then: ssh <host>"
print "If macOS blocks AgentJump, open System Settings > Privacy & Security and choose Open Anyway."
print "Browser agent:// links open a new iTerm/Terminal window."
