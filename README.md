# topsag-ssh

适用于 macOS 的 TopSAG（天融信堡垒机）非官方辅助工具，与天融信官方无隶属关系。

主要提供两项功能：

- 在当前终端通过 `ssh <host>` 登录已配置的资产。
- 通过未签名的 AgentJump.app 接管网页控制台的 `agent://` 链接，在新的 iTerm 窗口中建立连接；无法启动 iTerm 时回退到系统“终端”。

堡垒机地址、用户名和主机别名保存在 `~/.config/topsag-ssh/config.toml`，密码保存在 macOS 钥匙串（Keychain）中。请勿将凭据提交到仓库。

## 安装

运行环境为 macOS 和 zsh。克隆仓库后，在仓库目录中执行：

```sh
./install.sh
```

安装向导会询问：

- 堡垒机地址。
- 登录用户名。
- SSH 主机别名，例如 `web`。
- 是否跳过 TLS 证书验证。

随后，安装脚本会将文件安装到 `~/.local/share/topsag-ssh`，写入配置，将密码保存到钥匙串，构建 `~/Applications/AgentJump.app`，并在 `~/.zshrc` 中添加 zsh 代理脚本的加载语句。如果本工具的 iTerm 动态配置文件尚不存在，还会自动创建该文件。

安装完成后，请打开新的终端窗口。

如果 macOS 提示无法验证 AgentJump：

1. `install.sh` 已尝试执行 `xattr -dr com.apple.quarantine`，移除隔离属性。
2. 如果仍被拦截，进入“系统设置 > 隐私与安全性”，选择“仍要打开”。
3. 浏览器首次跳转时可能询问是否允许打开 AgentJump，请选择允许。

## SSH 用法

```sh
ssh web                 # 交互式会话
ssh web 'hostname; uptime'
ssh -o BatchMode=yes -o ConnectTimeout=8 web 'cat /etc/hosts'
```

安装脚本会在 `~/.local/bin/ssh` 创建包装脚本，并通过 `~/.zshenv` 将该目录放到 `PATH` 最前面。因此，使用此 `PATH` 查找 `ssh` 的工具都能通过它连接，包括新终端、`zsh -c`、Python `subprocess` 和 Git 的 SSH 调用。系统的 `/usr/bin/ssh` 不会被替换；不读取 shell `PATH` 的图形应用仍会调用系统 SSH。

仅拦截 `~/.config/topsag-ssh/hosts` 中列出的主机别名。`ssh -V` 和其他主机的连接仍交给系统 SSH 处理。

执行单次远程命令时会强制分配伪终端（PTY），以规避堡垒机在标准输出达到约 8 KB 时断开非 TTY 执行会话的问题。

SSH 连接期间，工具会向 `/mgt/keep/keepAlive` 发送心跳，防止网页令牌过期导致资产会话断开。

## 配置

完整示例见 [share/config.toml.example](share/config.toml.example)。最小配置如下：

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

可以用 `asset_name` 代替 `asset_index`，按资产名称或 IP 选择目标。修改主机配置后，执行以下命令更新主机别名列表：

```sh
python3 ~/.local/share/topsag-ssh/python/topsag_ssh.py --write-hosts-file
```

也可以重新运行 `./install.sh`。如需设置或更新密码，执行：

```sh
python3 ~/.local/share/topsag-ssh/python/topsag_ssh.py --configure
```

## 网页跳转

网页控制台生成的链接格式仍为 `agent://command&...&`。macOS 同一时间只能由一个应用接管该协议。`install.sh` 会注册 AgentJump.app，由它调用已安装的 `macos/agent_jump.py`。网页已生成短期有效的连接参数，因此该跳转流程无需再通过命令行登录堡垒机。

## 卸载

```sh
./uninstall.sh          # 保留配置和钥匙串条目
./uninstall.sh --purge  # 同时删除 ~/.config/topsag-ssh 配置目录
```

两种卸载方式都会保留钥匙串条目。

## 说明

- 验证码识别（OCR）在本地完成，属于可选功能。识别失败时，可在交互式终端中查看验证码图片并手动输入。
- v1 仅支持 macOS 和 zsh，暂未提供 Homebrew 安装配方，应用也未使用 Developer ID 签名。
