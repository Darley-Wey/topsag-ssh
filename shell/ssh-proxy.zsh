# topsag-ssh zsh proxy. Source this file from ~/.zshrc.
# Intercepts only host names listed in ~/.config/topsag-ssh/hosts.

if ! typeset -f _topsag_ssh_system >/dev/null; then
    _topsag_ssh_system() {
        command ssh "$@"
    }
fi

_topsag_ssh_prefix="${TOPSAG_SSH_PREFIX:-$HOME/.local/share/topsag-ssh}"
_topsag_ssh_hosts_file="${TOPSAG_SSH_HOSTS_FILE:-$HOME/.config/topsag-ssh/hosts}"
_topsag_ssh_python="${TOPSAG_SSH_PYTHON:-/usr/bin/python3}"

_topsag_ssh_load_hosts() {
    local -a names=()
    local line
    if [[ -n "${TOPSAG_SSH_HOSTS:-}" ]]; then
        names=(${(s: :)TOPSAG_SSH_HOSTS})
    elif [[ -f "$_topsag_ssh_hosts_file" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            line="${line%%#*}"
            line="${line//[[:space:]]/}"
            [[ -z "$line" ]] && continue
            names+=("$line")
        done < "$_topsag_ssh_hosts_file"
    fi
    print -r -- "${(j: :)names}"
}

_topsag_ssh_is_simple_name() {
    local host="$1"
    [[ "$host" != *.* && "$host" != *@* && "$host" != *:* && "$host" != /* ]]
}

function ssh() {
    emulate -L zsh
    setopt local_options no_nomatch

    local -a ssh_args=("$@")
    integer index=1
    local argument dest=""
    local -a hosts
    hosts=(${(z)$(_topsag_ssh_load_hosts)})

    while (( index <= ${#ssh_args} )); do
        argument="${ssh_args[index]}"
        case "$argument" in
            -o|-p|-l|-i|-F|-J|-E|-b|-c|-D|-e|-I|-m|-Q|-R|-W|-w|-B)
                (( index += 2 ))
                ;;
            -*)
                (( index += 1 ))
                ;;
            *)
                dest="$argument"
                break
                ;;
        esac
    done

    if [[ -n "$dest" && ${hosts[(Ie)$dest]} -ne 0 ]]; then
        shift "$index"
        local python_script="$_topsag_ssh_prefix/python/topsag_ssh.py"
        if [[ ! -f "$python_script" ]]; then
            print -u2 "topsag-ssh is not installed. Run install.sh from the repository."
            return 2
        fi
        if (( $# == 0 )); then
            "$_topsag_ssh_python" -W ignore "$python_script" --host "$dest"
            return $?
        fi
        "$_topsag_ssh_python" -W ignore "$python_script" --host "$dest" --remote-command "$*"
        return $?
    fi

    if (( ${#hosts} == 0 )) && [[ -n "$dest" ]] && _topsag_ssh_is_simple_name "$dest"; then
        print -u2 "topsag-ssh is not configured. Run install.sh or add [[hosts]] to ~/.config/topsag-ssh/config.toml."
        return 2
    fi

    _topsag_ssh_system "$@"
}
