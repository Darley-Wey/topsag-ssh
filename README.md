# topsag-ssh

Unofficial macOS helper for TopSAG / 天融信堡垒机. It is not affiliated with Topsec.

It does two jobs:

- `ssh <host>` logs into a configured asset in the current terminal
- an unsigned AgentJump.app handles `agent://` links from the web console in a new iTerm window

Bastion URL, username, and host names live in `~/.config/topsag-ssh/config.toml`. Passwords stay in Keychain. Do not put credentials in the repo.

## Install

macOS + zsh. From a clone:

```sh
./install.sh
```

The wizard asks for:

- bastion URL
- username
- SSH host name (for example `web`)
- whether to skip TLS verification

It then installs files to `~/.local/share/topsag-ssh`, writes the config, stores the password in Keychain, builds `~/Applications/AgentJump.app`, sources the zsh proxy from `~/.zshrc`, and adds an iTerm Dynamic Profile if none exists.

Open a new terminal afterwards.

If macOS says AgentJump cannot be verified:

1. `install.sh` already runs `xattr -dr com.apple.quarantine`
2. System Settings > Privacy & Security > Open Anyway
3. The first browser jump may ask to open AgentJump; allow it

## SSH usage

```sh
ssh web                 # interactive session
ssh web 'hostname; uptime'
ssh -o BatchMode=yes -o ConnectTimeout=8 web 'cat /etc/hosts'
```

Install puts a wrapper at `~/.local/bin/ssh` and prepends that directory to PATH from `~/.zshenv`, so any tool that finds `ssh` on PATH is covered: new terminals, `zsh -c`, Python `subprocess`, and Git's SSH calls. It is not a replacement for `/usr/bin/ssh`. GUI apps that ignore your shell PATH still call the system binary.

Only names listed in `~/.config/topsag-ssh/hosts` are intercepted. `ssh -V` and normal hosts still use system SSH.

One-shot commands force a PTY. This bastion drops non-TTY exec sessions around 8KB of stdout.

While SSH is up, the helper heartbeats `/mgt/keep/keepAlive` so the web token does not expire and kill the asset session.

## Config

See `share/config.toml.example`. A minimal file:

```toml
base_url = "https://bastion.example.com"
username = "alice@default"
insecure = false
language = "zh-cn"

[[hosts]]
name = "web"
asset_index = 0
protocol = "SSH"
```

`asset_name` can replace `asset_index`. After editing hosts, run:

```sh
python3 ~/.local/share/topsag-ssh/python/topsag_ssh.py --write-hosts-file
```

Or rerun `./install.sh`. Password:

```sh
python3 ~/.local/share/topsag-ssh/python/topsag_ssh.py --configure
```

## Web jump

The console still emits `agent://command&...&`. Only one macOS handler can own that scheme. `install.sh` registers AgentJump.app, which calls the installed `macos/agent_jump.py`. That path does not need CLI login; the page already created the short-lived payload.

## Uninstall

```sh
./uninstall.sh          # keep config and Keychain
./uninstall.sh --purge  # also delete ~/.config/topsag-ssh
```

## Notes

- Protocol AES key and the `@Encrypted` fallback password come from the vendor Windows client. They are not your account password.
- Captcha OCR is local and optional. If it fails, the CLI prompts for the image.
- v1 is macOS / zsh only. There is no Homebrew formula and the app is not Developer ID signed.
