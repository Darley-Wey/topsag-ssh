#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(/usr/bin/mktemp -d /tmp/topsag-ssh-proxy.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

export TOPSAG_SSH_PREFIX="$ROOT"
export TOPSAG_SSH_HOSTS_FILE="$TMP/hosts"
export TOPSAG_SSH_PYTHON="/usr/bin/python3"
source "$ROOT/shell/ssh-proxy.zsh"

# Fake system ssh so pass-through is observable.
_topsag_ssh_system() {
    print -r -- "SYSTEM:$*"
}

# Unconfigured simple name
unset TOPSAG_SSH_HOSTS
: > "$TOPSAG_SSH_HOSTS_FILE"
if ssh web >/tmp/topsag-empty.err 2>&1; then
    print -u2 "expected unconfigured ssh web to fail"
    exit 1
fi
grep -q "not configured" /tmp/topsag-empty.err

# ssh -V and dotted hosts pass through
out="$(ssh -V 2>&1 || true)"
print -r -- "$out" | grep -q "SYSTEM:-V"

out="$(ssh user@example.com echo hi)"
[[ "$out" == "SYSTEM:user@example.com echo hi" ]]

# Configured host intercepts, including leading options.
print -r -- "web" > "$TOPSAG_SSH_HOSTS_FILE"
print -r -- "db" >> "$TOPSAG_SSH_HOSTS_FILE"

# Replace python with a stub by pointing PREFIX python script... use TOPSAG_SSH_PYTHON wrapper
stub="$TMP/python3"
cat > "$stub" <<'EOF'
#!/bin/zsh
print -r -- "PY:$*"
EOF
chmod +x "$stub"
export TOPSAG_SSH_PYTHON="$stub"
mkdir -p "$TMP/share-prefix/python"
# The proxy looks up $_topsag_ssh_prefix/python/topsag_ssh.py
# Reload prefix to tmp that contains a fake script.
export TOPSAG_SSH_PREFIX="$TMP/share-prefix"
print -r -- 'print fake' > "$TMP/share-prefix/python/topsag_ssh.py"
source "$ROOT/shell/ssh-proxy.zsh"

out="$(ssh web)"
[[ "$out" == "PY:-W ignore $TMP/share-prefix/python/topsag_ssh.py --host web" ]]

out="$(ssh -o BatchMode=yes -o ConnectTimeout=8 web 'ls -la')"
[[ "$out" == "PY:-W ignore $TMP/share-prefix/python/topsag_ssh.py --host web --remote-command ls -la" ]]

out="$(ssh db 'hostname')"
[[ "$out" == "PY:-W ignore $TMP/share-prefix/python/topsag_ssh.py --host db --remote-command hostname" ]]

out="$(ssh example.com uptime)"
[[ "$out" == "SYSTEM:example.com uptime" ]]

print "SSH_PROXY_OK"
