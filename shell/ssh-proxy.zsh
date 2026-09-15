# topsag-ssh shell helper.
# The real intercept is ~/.local/bin/ssh. This file only keeps that wrapper
# first on PATH and drops any leftover ssh shell function.

if typeset -f ssh >/dev/null; then
    unfunction ssh
fi

if [[ -d "$HOME/.local/bin" ]]; then
    if (( ${path[(Ie)$HOME/.local/bin]} == 0 )); then
        path=("$HOME/.local/bin" $path)
        export PATH
    fi
fi
