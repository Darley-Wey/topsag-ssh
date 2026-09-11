"""Load and write the user-level topsag-ssh TOML config."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class ConfigError(ValueError):
    pass


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "topsag-ssh"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_HOSTS_PATH = DEFAULT_CONFIG_DIR / "hosts"


@dataclass
class HostConfig:
    name: str
    asset_index: int = 0
    account_index: int = 0
    protocol: str = "SSH"
    asset_name: str = ""


@dataclass
class AppConfig:
    base_url: str = ""
    username: str = ""
    insecure: bool = False
    language: str = "zh-cn"
    hosts: List[HostConfig] = field(default_factory=list)

    def host_named(self, name: str) -> HostConfig:
        for host in self.hosts:
            if host.name == name:
                return host
        raise ConfigError(
            f"Host '{name}' is not in {config_path()}. "
            "Add a [[hosts]] table or rerun install.sh."
        )


def config_path() -> Path:
    override = os.environ.get("TOPSAG_SSH_CONFIG")
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_PATH


def hosts_path() -> Path:
    override = os.environ.get("TOPSAG_SSH_HOSTS_FILE")
    if override:
        return Path(override).expanduser()
    return DEFAULT_HOSTS_PATH


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return bytes(value[1:-1], "utf-8").decode("unicode_escape")
    if value.lower() in {"true", "false"}:
        return value.lower()
    return value


def _parse_scalar(raw: str):
    value = _unquote(raw)
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def load_config(path: Optional[Path] = None) -> AppConfig:
    target = path or config_path()
    if not target.is_file():
        raise ConfigError(
            f"Missing config file {target}. Run install.sh from the topsag-ssh repo."
        )
    text = target.read_text(encoding="utf-8")
    config = AppConfig()
    current: Optional[HostConfig] = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "[[hosts]]":
            current = HostConfig(name="")
            config.hosts.append(current)
            continue
        if "=" not in line:
            continue
        key, raw_value = [part.strip() for part in line.split("=", 1)]
        value = _parse_scalar(raw_value)
        if current is None:
            if key in {"base_url", "username", "language"} and not isinstance(value, str):
                value = str(value)
            if hasattr(config, key):
                setattr(config, key, value)
            continue
        if hasattr(current, key):
            setattr(current, key, value)
    if not str(config.base_url).strip():
        raise ConfigError(f"{target} is missing base_url.")
    config.base_url = str(config.base_url).rstrip("/")
    named = []
    for host in config.hosts:
        name = host.name.strip()
        if not name:
            raise ConfigError("Each [[hosts]] table needs a name.")
        if name in named:
            raise ConfigError(f"Duplicate host name '{name}'.")
        named.append(name)
        host.name = name
        host.protocol = str(host.protocol or "SSH")
    return config


def render_config(config: AppConfig) -> str:
    lines = [
        f'base_url = "{config.base_url}"',
        f'username = "{config.username}"',
        f"insecure = {'true' if config.insecure else 'false'}",
        f'language = "{config.language}"',
        "",
    ]
    if not config.hosts:
        lines.append("# [[hosts]]")
        lines.append('# name = "web"')
        lines.append("# asset_index = 0")
        lines.append('# protocol = "SSH"')
        lines.append("")
    for host in config.hosts:
        lines.append("[[hosts]]")
        lines.append(f'name = "{host.name}"')
        lines.append(f"asset_index = {int(host.asset_index)}")
        lines.append(f"account_index = {int(host.account_index)}")
        lines.append(f'protocol = "{host.protocol}"')
        if host.asset_name:
            lines.append(f'asset_name = "{host.asset_name}"')
        lines.append("")
    return "\n".join(lines)


def write_config(config: AppConfig, path: Optional[Path] = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_config(config), encoding="utf-8")
    hosts_target = hosts_path() if path is None else target.parent / "hosts"
    write_hosts_file(config, hosts_target)
    return target


def write_hosts_file(config: AppConfig, path: Optional[Path] = None) -> Path:
    target = path or hosts_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    names = [host.name for host in config.hosts]
    target.write_text(("\n".join(names) + ("\n" if names else "")), encoding="utf-8")
    return target


def keychain_account(base_url: str, username: str) -> str:
    return f"{base_url.rstrip('/')}|{username}"
