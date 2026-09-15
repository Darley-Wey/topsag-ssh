#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(/usr/bin/mktemp -d /tmp/topsag-ssh-proxy.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

export TOPSAG_SSH_PREFIX="$TMP/share-prefix"
export TOPSAG_SSH_HOSTS_FILE="$TMP/hosts"
export TOPSAG_SSH_PYTHON="$TMP/python3"
export TOPSAG_REAL_SSH="$TMP/real-ssh"
unset TOPSAG_SSH_HOSTS

mkdir -p "$TMP/share-prefix/python"
print -r -- 'print fake' > "$TMP/share-prefix/python/topsag_ssh.py"

cat > "$TMP/python3" <<'EOF'
#!/bin/zsh
print -r -- "PY:$*"
EOF
chmod +x "$TMP/python3"

cat > "$TMP/real-ssh" <<'EOF'
#!/bin/zsh
print -r -- "SYSTEM:$*"
EOF
chmod +x "$TMP/real-ssh"

wrapper="$ROOT/bin/ssh"
chmod +x "$wrapper"

: > "$TOPSAG_SSH_HOSTS_FILE"
out="$("$wrapper" -V)"
[[ "$out" == "SYSTEM:-V" ]]

out="$("$wrapper" user@example.com echo hi)"
[[ "$out" == "SYSTEM:user@example.com echo hi" ]]

print -r -- "web" > "$TOPSAG_SSH_HOSTS_FILE"
print -r -- "db" >> "$TOPSAG_SSH_HOSTS_FILE"

out="$("$wrapper" web)"
[[ "$out" == "PY:-W ignore $TMP/share-prefix/python/topsag_ssh.py --host web" ]]

out="$("$wrapper" -o BatchMode=yes -o ConnectTimeout=8 web 'ls -la')"
[[ "$out" == "PY:-W ignore $TMP/share-prefix/python/topsag_ssh.py --host web --remote-command ls -la" ]]

out="$("$wrapper" db hostname)"
[[ "$out" == "PY:-W ignore $TMP/share-prefix/python/topsag_ssh.py --host db --remote-command hostname" ]]

out="$("$wrapper" example.com uptime)"
[[ "$out" == "SYSTEM:example.com uptime" ]]

print "SSH_PROXY_OK"
