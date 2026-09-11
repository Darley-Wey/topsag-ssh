#!/usr/bin/env python3
"""Create and launch a fresh TopSAG SSH session.

Credentials stay in macOS Keychain. Bastion URL, username, and SSH host names
come from ~/.config/topsag-ssh/config.toml.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

import argparse
import base64
import getpass
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from config import (
    AppConfig,
    ConfigError,
    HostConfig,
    config_path,
    hosts_path,
    keychain_account,
    load_config,
    write_config,
    write_hosts_file,
)
from crypto import (
    LEGACY_FALLBACK_PASSWORD,
    base_aes_decrypt,
    base_aes_encrypt,
    compact_json,
    parse_agent_scheme,
)

DEFAULT_LANGUAGE = "zh-cn"
DEFAULT_CLIENT = "terminal"

# Eight representative 24x32 binary glyphs per digit, compressed with zlib and
# encoded as base64. They were built from local captcha samples and keep OCR
# fully offline.
CAPTCHA_TEMPLATES_B64 = (
    "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"
    "OxKjZWI0A///AaGvPYk="
)

USERNAME_SERVICE = "topsag-ssh-username"
PASSWORD_SERVICE = "topsag-ssh-password"
SESSION_SERVICE = "topsag-ssh-session"

CLIENT_OPTYPES = {
    "terminal": "1",
    "xshell": "1",
    "putty": "3",
    "securecrt": "2",
}

AUTH_EXPIRED_STATUSES = {5008, 5046, 5047}


class LauncherError(RuntimeError):
    pass


class AuthExpired(LauncherError):
    pass


class CaptchaRejected(LauncherError):
    pass


class CaptchaUnreadable(LauncherError):
    pass


@dataclass
class SessionState:
    token: str
    user_info: Dict[str, Any]
    company_alias: str


@dataclass
class SelectedTarget:
    asset: Dict[str, Any]
    account: Dict[str, Any]
    protocol: Dict[str, Any]


def _argv_has(*flags: str) -> bool:
    for argument in sys.argv[1:]:
        for flag in flags:
            if argument == flag or argument.startswith(flag + "="):
                return True
    return False


def apply_config(args: argparse.Namespace) -> AppConfig:
    try:
        config = load_config()
    except ConfigError as exc:
        if args.configure:
            args.app_config = None
            if not args.base_url:
                if not sys.stdin.isatty():
                    raise LauncherError(str(exc)) from exc
                args.base_url = input("Bastion URL: ").strip().rstrip("/")
            if not args.base_url:
                raise LauncherError("base_url is required.")
            return AppConfig(base_url=args.base_url)
        raise LauncherError(str(exc)) from exc

    args.app_config = config
    if not args.base_url:
        args.base_url = config.base_url
    if not args.username and config.username:
        args.username = config.username
    if not _argv_has("--insecure"):
        args.insecure = bool(config.insecure)
    if not _argv_has("--language"):
        args.language = config.language or DEFAULT_LANGUAGE
    if args.host:
        host = config.host_named(args.host)
        if not _argv_has("--asset-index"):
            args.asset_index = int(host.asset_index)
        if not _argv_has("--account-index"):
            args.account_index = int(host.account_index)
        if not _argv_has("--protocol"):
            args.protocol = host.protocol or args.protocol
        if not _argv_has("--asset-name") and host.asset_name:
            args.asset_name = host.asset_name
    elif not args.configure and not args.write_hosts_file and not args.token_stdin:
        if len(config.hosts) == 1:
            args.host = config.hosts[0].name
            return apply_config(args)
        raise LauncherError(
            "Pass --host NAME, matching a [[hosts]] entry in "
            f"{config_path()}."
        )
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and launch a fresh TopSAG SSH session."
    )
    parser.add_argument("--host", help="SSH host name from config.toml [[hosts]].")
    parser.add_argument("--base-url", help="Override bastion URL from config.toml.")
    parser.add_argument("--username", help="Login name. '@default' is added when omitted.")
    parser.add_argument(
        "--password-env",
        default="TOPSAG_PASSWORD",
        help="Environment variable containing the password (default: TOPSAG_PASSWORD).",
    )
    parser.add_argument("--captcha", help="Captcha digits. Overrides automatic recognition.")
    parser.add_argument(
        "--no-captcha-auto",
        action="store_true",
        help="Disable local OCR and use the captcha prompt instead.",
    )
    parser.add_argument(
        "--captcha-attempts",
        type=int,
        default=5,
        help="Maximum automatic captcha/login attempts (default: 5).",
    )
    parser.add_argument(
        "--captcha-file",
        default=str(Path.home() / "Library/Caches/topsag-ssh/captcha.png"),
        help="Where to save the current captcha image.",
    )
    parser.add_argument(
        "--no-open-captcha",
        action="store_true",
        help="Do not open the captcha image before prompting.",
    )
    parser.add_argument(
        "--client",
        choices=sorted(CLIENT_OPTYPES),
        default=os.environ.get("TOPSAG_CLIENT", DEFAULT_CLIENT),
        help="Where to open the session (default: this terminal).",
    )
    parser.add_argument(
        "--asset-index",
        type=int,
        default=0,
        help="Zero-based asset index in /mgt/asset/listOfOperational (default: 0).",
    )
    parser.add_argument(
        "--account-index",
        type=int,
        default=0,
        help="Zero-based account index when --protocol is not supplied (default: 0).",
    )
    parser.add_argument("--asset-name", default="", help="Select an asset by name or IP.")
    parser.add_argument(
        "--protocol",
        help="Prefer an account with this protocol, for example SSH.",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Prompt for and save the username and password in macOS Keychain.",
    )
    parser.add_argument(
        "--write-hosts-file",
        action="store_true",
        help="Rewrite ~/.config/topsag-ssh/hosts from config.toml and exit.",
    )
    parser.add_argument(
        "--forget-session",
        action="store_true",
        help="Delete the cached login session before running.",
    )
    parser.add_argument(
        "--token-stdin",
        action="store_true",
        help="Read a JSON session from stdin instead of Keychain. Useful for diagnostics.",
    )
    parser.add_argument(
        "--no-cache-session",
        action="store_true",
        help="Do not save the refreshed token/session to Keychain.",
    )
    parser.add_argument(
        "--print-scheme",
        action="store_true",
        help="Print the generated agent URI. Treat the output as sensitive.",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Generate the session but do not connect.",
    )
    parser.add_argument(
        "--remote-command",
        help=(
            "Execute one remote shell command on the selected asset and exit. "
            "The remote command's exit status is returned."
        ),
    )
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS verification for a self-signed deployment.",
    )
    args = parser.parse_args()
    args.asset_name = args.asset_name or ""
    args.app_config = None
    apply_config(args)
    return args


def normalize_username(username: str) -> str:
    username = username.strip()
    if not username:
        raise LauncherError("Username cannot be empty.")
    if "@" not in username:
        return username + "@default"
    return username


def make_session(args: argparse.Namespace) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Origin": args.base_url.rstrip("/"),
            "Referer": args.base_url.rstrip("/") + "/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        }
    )
    return session


def request_json(
    session: requests.Session,
    args: argparse.Namespace,
    method: str,
    path: str,
    *,
    token: Optional[str] = None,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    expect_image: bool = False,
) -> requests.Response:
    headers: Dict[str, str] = {}
    if token:
        headers["token"] = token
    response = session.request(
        method,
        args.base_url.rstrip("/") + path,
        headers=headers,
        json=json_body,
        params=params,
        timeout=args.timeout,
        verify=not args.insecure,
    )
    response.raise_for_status()
    if expect_image:
        return response
    try:
        payload = response.json()
    except ValueError as exc:
        raise LauncherError(f"Non-JSON response from {path}: {response.text[:200]}") from exc
    if isinstance(payload, dict):
        status = payload.get("status")
        if status in AUTH_EXPIRED_STATUSES:
            raise AuthExpired(str(payload.get("msg") or "Token expired"))
    return response


def keychain_get(service: str, account: Optional[str] = None) -> Optional[str]:
    if sys.platform != "darwin":
        return None
    command = ["security", "find-generic-password", "-w", "-s", service]
    if account:
        command.extend(["-a", account])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    value = result.stdout.rstrip("\n")
    if (
        service == SESSION_SERVICE
        and value
        and len(value) % 2 == 0
        and all(character in "0123456789abcdefABCDEF" for character in value)
    ):
        try:
            decoded = bytes.fromhex(value).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded = ""
        if decoded.startswith("{"):
            value = decoded
    return value or None


def keychain_set(service: str, value: str, account: Optional[str] = None) -> None:
    if sys.platform != "darwin":
        return
    command = [
        "security",
        "add-generic-password",
        "-U",
        "-s",
        service,
        "-a",
        account or "default",
        "-w",
        value,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise LauncherError(f"Unable to write macOS Keychain item '{service}': {detail}")


def keychain_delete(service: str, account: Optional[str] = None) -> None:
    if sys.platform != "darwin":
        return
    for _ in range(10):
        command = ["security", "delete-generic-password", "-s", service]
        if account:
            command.extend(["-a", account])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return


def credential_account(args: argparse.Namespace, username: str) -> str:
    return keychain_account(args.base_url, username)


def get_username(args: argparse.Namespace) -> str:
    username = args.username or os.environ.get("TOPSAG_USERNAME")
    if not username:
        if not sys.stdin.isatty():
            raise LauncherError("Username is required. Set it in config.toml or pass --username.")
        username = input("TopSAG username: ").strip()
    return normalize_username(username)


def get_password(args: argparse.Namespace, normalized_username: str) -> str:
    account = credential_account(args, normalized_username)
    password = os.environ.get(args.password_env) or keychain_get(PASSWORD_SERVICE, account)
    if password:
        return password
    if not sys.stdin.isatty():
        raise LauncherError(
            f"Password not set. Export {args.password_env} or run --configure."
        )
    password = getpass.getpass("TopSAG password: ")
    if not password:
        raise LauncherError("Password cannot be empty.")
    if not args.no_cache_session:
        try:
            keychain_set(PASSWORD_SERVICE, password, account)
        except LauncherError as exc:
            print(f"Warning: {exc}", file=sys.stderr)
    return password


def load_cached_session(args: argparse.Namespace, username: str) -> Optional[SessionState]:
    raw = keychain_get(SESSION_SERVICE, credential_account(args, username))
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return SessionState(
            token=str(value["token"]),
            user_info=dict(value["user_info"]),
            company_alias=str(value["company_alias"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def save_cached_session(args: argparse.Namespace, state: SessionState, username: str) -> None:
    raw = compact_json(
        {
            "token": state.token,
            "user_info": state.user_info,
            "company_alias": state.company_alias,
        }
    )
    keychain_set(SESSION_SERVICE, raw, credential_account(args, username))


def read_session_stdin() -> SessionState:
    raw = sys.stdin.read().strip()
    if not raw:
        raise LauncherError("--token-stdin was supplied, but stdin was empty.")
    try:
        value = json.loads(raw)
        return SessionState(
            token=str(value["token"]),
            user_info=dict(value["user_info"]),
            company_alias=str(value["company_alias"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LauncherError(
            "--token-stdin expects JSON: "
            '{"token":"...","user_info":{...},"company_alias":"..."}'
        ) from exc


_CAPTCHA_TEMPLATE_CACHE: Optional[list[Tuple[str, bytes]]] = None


def load_captcha_templates() -> list[Tuple[str, bytes]]:
    global _CAPTCHA_TEMPLATE_CACHE
    if _CAPTCHA_TEMPLATE_CACHE is not None:
        return _CAPTCHA_TEMPLATE_CACHE
    try:
        raw = zlib.decompress(base64.b64decode(CAPTCHA_TEMPLATES_B64))
    except (ValueError, zlib.error) as exc:
        raise CaptchaUnreadable("Embedded captcha templates are corrupted.") from exc
    glyph_size = 24 * 32
    expected_size = 10 * 8 * glyph_size
    if len(raw) != expected_size:
        raise CaptchaUnreadable("Embedded captcha templates have an invalid size.")
    templates: list[Tuple[str, bytes]] = []
    offset = 0
    for digit in "0123456789":
        for _ in range(8):
            templates.append((digit, raw[offset : offset + glyph_size]))
            offset += glyph_size
    _CAPTCHA_TEMPLATE_CACHE = templates
    return templates


def captcha_components(mask: Any) -> list[list[Tuple[int, int]]]:
    width, height = mask.size
    pixels = mask.load()
    seen: set[Tuple[int, int]] = set()
    components: list[list[Tuple[int, int]]] = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0 or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            component: list[Tuple[int, int]] = []
            while stack:
                px, py = stack.pop()
                component.append((px, py))
                for ny in range(max(0, py - 1), min(height, py + 2)):
                    for nx in range(max(0, px - 1), min(width, px + 2)):
                        if pixels[nx, ny] == 0 or (nx, ny) in seen:
                            continue
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            components.append(component)
    return components


def split_captcha_digits(image_bytes: bytes) -> list[bytes]:
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:
        raise CaptchaUnreadable(
            "Automatic captcha recognition needs Pillow. Install it with: "
            "python3 -m pip install Pillow"
        ) from exc

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    gray = ImageOps.grayscale(image)
    mask = (
        gray.filter(ImageFilter.MaxFilter(3))
        .filter(ImageFilter.MinFilter(3))
        .point(lambda value: 255 if value < 225 else 0)
    )
    candidates: list[Tuple[int, int, int, int]] = []
    for component in captcha_components(mask):
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        box = min(xs), min(ys), max(xs) + 1, max(ys) + 1
        width, height = box[2] - box[0], box[3] - box[1]
        if len(component) < 150 or height < 30 or width < 8:
            continue
        candidates.append(box)

    merged: list[Tuple[int, int, int, int]] = []
    for box in sorted(candidates):
        x0, y0, x1, y1 = box
        for index, current in enumerate(merged):
            cx0, cy0, cx1, cy1 = current
            overlap = min(x1, cx1) - max(x0, cx0)
            gap = max(x0, cx0) - min(x1, cx1)
            if overlap > 0 or gap <= 2:
                merged[index] = (
                    min(x0, cx0),
                    min(y0, cy0),
                    max(x1, cx1),
                    max(y1, cy1),
                )
                break
        else:
            merged.append(box)

    split: list[Tuple[int, int, int, int]] = []
    for x0, y0, x1, y1 in merged:
        if x1 - x0 <= 58:
            split.append((x0, y0, x1, y1))
            continue
        columns = [
            sum(1 for y in range(y0, y1) if mask.getpixel((x, y)) == 0)
            for x in range(x0, x1)
        ]
        start = len(columns) // 4
        end = len(columns) * 3 // 4
        split_at = x0 + start + columns[start:end].index(min(columns[start:end]))
        split.append((x0, y0, split_at, y1))
        split.append((split_at, y0, x1, y1))

    if len(split) != 4:
        raise CaptchaUnreadable(
            f"Could not split captcha into four digits (found {len(split)})."
        )

    glyph_size = (24, 32)
    glyphs: list[bytes] = []
    for box in sorted(split):
        character = mask.crop(box)
        bounds = character.getbbox()
        if not bounds:
            raise CaptchaUnreadable("Captcha contained an empty digit region.")
        character = character.crop(bounds)
        scale = min(
            (glyph_size[0] - 4) / character.width,
            (glyph_size[1] - 4) / character.height,
        )
        resized = character.resize(
            (
                max(1, round(character.width * scale)),
                max(1, round(character.height * scale)),
            ),
            Image.Resampling.NEAREST,
        )
        canvas = Image.new("L", glyph_size)
        canvas.paste(
            resized,
            (
                (glyph_size[0] - resized.width) // 2,
                (glyph_size[1] - resized.height) // 2,
            ),
        )
        glyphs.append(bytes(1 if value else 0 for value in canvas.getdata()))
    return glyphs


def recognize_captcha(image_bytes: bytes) -> Tuple[str, float, float]:
    templates = load_captcha_templates()
    recognized: list[str] = []
    confidences: list[float] = []
    for glyph in split_captcha_digits(image_bytes):
        distances: list[Tuple[int, str]] = []
        for digit in "0123456789":
            best = min(
                sum(left != right for left, right in zip(glyph, template))
                for template_digit, template in templates
                if template_digit == digit
            )
            distances.append((best, digit))
        distances.sort()
        best_distance, digit = distances[0]
        second_distance = next(
            distance for distance, candidate in distances if candidate != digit
        )
        if best_distance > 144:
            raise CaptchaUnreadable("Captcha digit did not match the local glyph model.")
        recognized.append(digit)
        margin = math.sqrt(second_distance) - math.sqrt(best_distance)
        confidences.append(max(0.0, min(1.0, 0.45 + margin / 12.0)))

    return "".join(recognized), sum(confidences) / len(confidences), min(confidences)


def fetch_captcha(
    session: requests.Session,
    args: argparse.Namespace,
    captcha_path: Path,
) -> bytes:
    response = request_json(
        session,
        args,
        "GET",
        "/mgt/login/code",
        params={"timestamp": int(time.time() * 1000)},
        expect_image=True,
    )
    if "image" not in response.headers.get("Content-Type", ""):
        raise LauncherError("Captcha endpoint did not return an image.")
    captcha_path.parent.mkdir(parents=True, exist_ok=True)
    captcha_path.write_bytes(response.content)
    return response.content


def prompt_captcha(args: argparse.Namespace, captcha_path: Path) -> str:
    if sys.platform == "darwin" and not args.no_open_captcha:
        subprocess.Popen(
            ["open", str(captcha_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not sys.stdin.isatty():
        raise LauncherError("Captcha is required. Pass --captcha or run in a terminal.")
    captcha = input(f"Captcha ({captcha_path}): ").strip()
    if not captcha:
        raise LauncherError("Captcha cannot be empty.")
    return captcha


def login(
    session: requests.Session,
    args: argparse.Namespace,
    normalized_username: str,
    password: str,
) -> SessionState:
    status_response = request_json(session, args, "GET", "/mgt/login/imgCodeStatus")
    image_status = status_response.json()
    captcha_required = bool(image_status.get("data"))
    captcha_arg = args.captcha.strip() if args.captcha else ""
    captcha_path = Path(args.captcha_file).expanduser().resolve()

    def submit_captcha(captcha: str) -> SessionState:
        login_data = {
            "sUser": normalized_username,
            "sCharacter": base_aes_encrypt(password),
            "code": captcha,
            "language": args.language,
        }
        response = request_json(
            session,
            args,
            "POST",
            "/mgt/login/userNameAndPwdAuth",
            json_body={"sCode": base_aes_encrypt(compact_json(login_data))},
        )
        payload = response.json()
        status = payload.get("status")
        if status == 200:
            data = payload.get("data") or {}
            token = data.get("token") or response.headers.get("token")
            if not token:
                raise LauncherError("Login succeeded but no token was returned.")
            encoded_user_info = data.get("userInfo")
            if not encoded_user_info:
                raise LauncherError("Login succeeded but userInfo was missing.")
            try:
                user_info = json.loads(base_aes_decrypt(str(encoded_user_info)))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise LauncherError("Unable to decode userInfo from login response.") from exc
            company_alias = (
                str(user_info.get("companyAlias") or "")
                or normalized_username.split("@", 1)[1]
            )
            return SessionState(
                token=str(token),
                user_info=dict(user_info),
                company_alias=company_alias,
            )

        if status == 5049:
            raise CaptchaRejected(str(payload.get("msg") or "Invalid captcha"))

        if status in {5043, 5042}:
            raise LauncherError(
                "The account requires an additional web login step "
                f"(status {status}). Complete that step in the browser first."
            )
        raise LauncherError(str(payload.get("msg") or f"Login failed with status {status}."))

    attempts = max(1, args.captcha_attempts) if captcha_required else 1
    last_error: Optional[CaptchaRejected] = None
    for attempt in range(1, attempts + 1):
        captcha = ""
        if captcha_required:
            image_bytes = fetch_captcha(session, args, captcha_path)
            if captcha_arg and attempt == 1:
                captcha = captcha_arg
            elif not args.no_captcha_auto and not captcha_arg:
                try:
                    captcha, average_confidence, minimum_confidence = recognize_captcha(
                        image_bytes
                    )
                except CaptchaUnreadable as exc:
                    print(
                        f"Captcha OCR uncertain ({exc}); refreshing and retrying "
                        f"({attempt}/{attempts}).",
                        file=sys.stderr,
                    )
                    continue
                print(
                    "Captcha recognized locally: "
                    f"{captcha} (min confidence {minimum_confidence:.0%}, "
                    f"average {average_confidence:.0%}).",
                    file=sys.stderr,
                )
            else:
                captcha = prompt_captcha(args, captcha_path)

        try:
            return submit_captcha(captcha)
        except CaptchaRejected as exc:
            last_error = exc
            print(
                f"Captcha rejected; refreshing and retrying ({attempt}/{attempts}).",
                file=sys.stderr,
            )

    manual_fallback = (
        captcha_required
        and not args.no_captcha_auto
        and sys.stdin.isatty()
    )
    if manual_fallback:
        print("Automatic recognition failed; falling back to manual input.", file=sys.stderr)
        fetch_captcha(session, args, captcha_path)
        try:
            return submit_captcha(prompt_captcha(args, captcha_path))
        except CaptchaRejected as exc:
            last_error = exc

    raise last_error or CaptchaRejected("Captcha was rejected.")


def list_assets(
    session: requests.Session,
    args: argparse.Namespace,
    state: SessionState,
) -> Tuple[requests.Response, Dict[str, Any]]:
    response = request_json(
        session,
        args,
        "POST",
        "/mgt/asset/listOfOperational",
        token=state.token,
        json_body={
            "page": {"limit": 100, "curPage": 1, "startIndex": 0},
            "keyword": "",
        },
    )
    payload = response.json()
    if payload.get("status") != 200:
        raise LauncherError(str(payload.get("msg") or "Unable to list assets."))
    data = payload.get("data") or {}
    if not data.get("list"):
        raise LauncherError("No authorized operational assets were returned.")
    return response, payload


def select_target(args: argparse.Namespace, payload: Dict[str, Any]) -> SelectedTarget:
    assets = payload["data"]["list"]
    asset = None
    if args.asset_name:
        needle = str(args.asset_name).strip().lower()
        asset = next(
            (
                item
                for item in assets
                if needle in str(item.get("assetName") or "").lower()
                or needle == str(item.get("assetIp") or "").lower()
            ),
            None,
        )
        if asset is None:
            raise LauncherError(f"No operational asset matched '{args.asset_name}'.")
    else:
        if args.asset_index < 0 or args.asset_index >= len(assets):
            raise LauncherError(f"Asset index {args.asset_index} is out of range.")
        asset = assets[args.asset_index]
    accounts = asset.get("account") or []
    if not accounts:
        raise LauncherError("The selected asset has no authorized accounts.")

    if args.protocol:
        requested = args.protocol.lower()
        account = next(
            (item for item in accounts if str(item.get("protocol", "")).lower() == requested),
            None,
        )
        if not account:
            raise LauncherError(
                f"The selected asset has no authorized {args.protocol} account."
            )
    else:
        if args.account_index < 0 or args.account_index >= len(accounts):
            raise LauncherError(f"Account index {args.account_index} is out of range.")
        account = accounts[args.account_index]

    protocol_name = str(account.get("protocol") or "")
    protocol = next(
        (item for item in (asset.get("protocols") or []) if item.get("name") == protocol_name),
        None,
    )
    if not protocol:
        raise LauncherError(f"Protocol metadata for {protocol_name} was not found.")
    if str(account.get("authType", "0")) == "1":
        raise LauncherError(
            "This account disables offline/local-client SSO; the web console is required."
        )
    return SelectedTarget(asset=asset, account=account, protocol=protocol)


def api_status(payload: Dict[str, Any], label: str) -> Any:
    status = payload.get("status")
    if status != 200:
        raise LauncherError(str(payload.get("msg") or f"{label} failed with status {status}."))
    return payload.get("data")


def build_agent_scheme(
    session: requests.Session,
    args: argparse.Namespace,
    state: SessionState,
    target: SelectedTarget,
) -> Tuple[str, Dict[str, Any]]:
    asset = target.asset
    account = target.account
    protocol = target.protocol
    user_info = state.user_info
    user_name = str(user_info.get("userName") or "")
    user_id = str(user_info.get("userId") or "")
    if not user_name or not user_id:
        raise LauncherError("Cached userInfo is missing userName or userId; login again with --forget-session.")

    protocol_name = str(account.get("protocol") or "")
    account_name = str(account.get("account") or "")
    asset_port = protocol.get("port")
    if asset_port is None:
        raise LauncherError(f"Protocol {protocol_name} has no port.")

    verify_response = request_json(
        session,
        args,
        "POST",
        "/mgt/account/insertVerifyPwd",
        token=state.token,
        json_body={
            "userId": user_id,
            "userName": user_name,
            "accountId": account.get("_id"),
            "accountName": account_name,
            "accountPwd": "",
            "ssoType": account.get("ssoType", "0"),
            "assetIp": asset.get("assetIp"),
            "protocol": protocol_name,
            "assetPort": asset_port,
            "serverIp": args.base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0],
            "operateType": "agent",
        },
    )
    temporary_user = api_status(verify_response.json(), "insertVerifyPwd")
    if not isinstance(temporary_user, str) or not temporary_user:
        raise LauncherError("insertVerifyPwd did not return a temporary server user.")

    user_info_response = request_json(
        session,
        args,
        "GET",
        "/opt/asset/findUserInfo",
        token=state.token,
        params={"userName": user_name},
    )
    server_password = api_status(user_info_response.json(), "findUserInfo")

    server_ip = args.base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    server_ip_response = request_json(
        session,
        args,
        "GET",
        "/config/sso/getServerIp",
        token=state.token,
    )
    server_ip_payload = server_ip_response.json()
    if server_ip_payload.get("status") == 200 and server_ip_payload.get("data"):
        server_ip = str(server_ip_payload["data"])

    sso_summary = {
        "companyAlias": state.company_alias,
        "userId": user_id,
        "userName": user_name,
        "assetId": asset.get("_id"),
        "assetIp": asset.get("assetIp"),
        "assetName": asset.get("assetName"),
        "accountId": account.get("_id"),
        "accName": account_name,
        "protocol": protocol_name,
        "loginType": "2",
        "userNameId": temporary_user,
        "accessName": "",
    }
    sso_response = request_json(
        session,
        args,
        "POST",
        "/opt/asset/offLine_getSSOStatus",
        token=state.token,
        json_body={"info": base_aes_encrypt(compact_json(sso_summary))},
    )
    sso_data = api_status(sso_response.json(), "offLine_getSSOStatus") or {}
    session_id = sso_data.get("conductAudit")
    if not session_id:
        raise LauncherError("offLine_getSSOStatus did not return conductAudit.")

    scheme_payload = {
        "serverIp": server_ip,
        "serverPort": "2222",
        "serverUser": temporary_user,
        "serverPwd": server_password,
        "assetIp": asset.get("assetIp"),
        "assetPort": asset_port,
        "assetUser": base64.b64encode(account_name.encode("utf-8")).decode("ascii"),
        "protocol": protocol_name,
        "alias": state.company_alias,
        "opType": CLIENT_OPTYPES[args.client],
        "uuid": "",
        "drive": "",
        "screen": "",
        "appServerIp": "",
        "appServerPort": "",
        "sessionId": session_id,
    }
    scheme = "agent://command&" + base_aes_encrypt(compact_json(scheme_payload)) + "&"
    return scheme, {
        "assetName": asset.get("assetName"),
        "assetIp": asset.get("assetIp"),
        "account": account_name,
        "protocol": protocol_name,
        "assetPort": asset_port,
        "client": args.client,
    }


def terminal_ssh_command(payload: Dict[str, Any]) -> Tuple[list[str], str]:
    alias = str(payload.get("alias") or "")
    session_id = str(payload.get("sessionId") or "")
    host = str(payload.get("serverIp") or "")
    port = str(payload.get("serverPort") or "2222")
    if not alias or not session_id or not host:
        raise LauncherError("Agent scheme is missing terminal connection fields.")

    # The bastion routes this one-time username to the target asset.
    user = base64.b64encode(f"{alias}@{session_id}".encode("utf-8")).decode("ascii")
    password = str(payload.get("serverPwd") or "")
    if not password or password == "@Encrypted":
        password = LEGACY_FALLBACK_PASSWORD
    protocol = str(payload.get("protocol") or "SSH").upper()
    auth_options = [
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "LogLevel=ERROR",
    ]
    if protocol in {"SFTP", "FTP"}:
        command = ["sftp"] + auth_options + [f"-oPort={port}", f"{user}@{host}"]
    else:
        command = ["ssh"] + auth_options + ["-p", port, f"{user}@{host}"]
    return command, password


def tcl_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    for source, replacement in (
        ('"', '\\"'),
        ("$", "\\$"),
        ("[", "\\["),
        ("]", "\\]"),
        ("\r", "\\r"),
        ("\n", "\\n"),
    ):
        escaped = escaped.replace(source, replacement)
    return f'"{escaped}"'


def ping_web_keepalive(
    args: argparse.Namespace,
    state: SessionState,
    *,
    quiet: bool = False,
) -> bool:
    endpoint = args.base_url.rstrip("/") + "/mgt/keep/keepAlive"
    try:
        response = requests.get(
            endpoint,
            headers={"token": state.token},
            timeout=min(args.timeout, 15.0),
            verify=not args.insecure,
        )
        payload = response.json()
        status = payload.get("status")
        if status in {200, 5045, 5048}:
            return True
        if not quiet:
            print(
                "TopSAG web keepalive stopped with status "
                f"{status}; the SSH session may be terminated.",
                file=sys.stderr,
            )
        return False
    except (requests.RequestException, ValueError) as exc:
        if not quiet:
            print(
                f"TopSAG web keepalive request failed: {type(exc).__name__}",
                file=sys.stderr,
            )
        return False


def keep_web_session_alive(
    args: argparse.Namespace,
    state: SessionState,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        if not ping_web_keepalive(args, state):
            return
        stop_event.wait(5.0)


def launch_scheme_in_current_terminal(
    scheme: str,
    args: argparse.Namespace,
    state: SessionState,
) -> int:
    if not args.remote_command and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise LauncherError(
            "The terminal client requires an interactive terminal. "
            "Run ssh <host> from a terminal or choose --client xshell."
        )
    expect_binary = None
    if not args.remote_command:
        expect_binary = shutil.which("expect")
        if not expect_binary:
            raise LauncherError(
                "The 'expect' command is required for automatic password entry."
            )

    command, password = terminal_ssh_command(parse_agent_scheme(scheme))
    if args.remote_command:
        if command[0] == "sftp":
            raise LauncherError("--remote-command is only supported for SSH clients.")
        # TopSAG's non-TTY exec channel drops the TCP session around 8KB of
        # stdout. Force a PTY so one-shot commands use the interactive path.
        if command[0] == "ssh":
            command.insert(1, "-tt")
        command.append(args.remote_command)

    script_path: Optional[Path] = None
    askpass_path: Optional[Path] = None
    keepalive_stop = threading.Event()
    keepalive_thread = threading.Thread(
        target=keep_web_session_alive,
        args=(args, state, keepalive_stop),
        daemon=True,
    )
    try:
        environment = os.environ.copy()
        environment["TOPSAG_SSH_PASSWORD"] = password
        ping_web_keepalive(args, state, quiet=True)
        keepalive_thread.start()

        if args.remote_command:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".sh", prefix="topsag_askpass_", delete=False
            ) as askpass:
                askpass.write('#!/bin/sh\nprintf "%s\\n" "$TOPSAG_SSH_PASSWORD"\n')
                askpass_path = Path(askpass.name)
            askpass_path.chmod(0o700)
            environment["SSH_ASKPASS"] = str(askpass_path)
            environment["SSH_ASKPASS_REQUIRE"] = "force"
            environment["DISPLAY"] = environment.get("DISPLAY", ":0")
            environment.setdefault("TERM", "dumb")
            result = subprocess.run(command, env=environment)
            return result.returncode

        real_command = " ".join(tcl_quote(argument) for argument in command)
        expect_script = (
            "set timeout 60\n"
            f"spawn {real_command}\n"
            "expect {\n"
            '    -re "(?i)password:" { send -- $env(TOPSAG_SSH_PASSWORD)\\r }\n'
            '    timeout { puts stderr "Timed out waiting for the SSH password prompt."; exit 124 }\n'
            "    eof { catch wait result; exit [lindex $result 3] }\n"
            "}\n"
            "interact\n"
            "catch wait result\n"
            "exit [lindex $result 3]\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".exp", prefix="topsag_", delete=False
        ) as script:
            script.write(expect_script)
            script_path = Path(script.name)
        result = subprocess.run([expect_binary, str(script_path)], env=environment)
        if result.returncode != 0:
            raise LauncherError(f"SSH session exited with status {result.returncode}.")
        return 0
    finally:
        keepalive_stop.set()
        if keepalive_thread.is_alive():
            keepalive_thread.join(timeout=1.0)
        if script_path is not None:
            script_path.unlink(missing_ok=True)
        if askpass_path is not None:
            askpass_path.unlink(missing_ok=True)


def launch_scheme(
    scheme: str,
    args: argparse.Namespace,
    state: SessionState,
) -> int:
    if args.client == "terminal":
        return launch_scheme_in_current_terminal(scheme, args, state)
    if sys.platform != "darwin":
        raise LauncherError("Automatic scheme launch is implemented for macOS only.")
    result = subprocess.run(["open", scheme], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise LauncherError(f"Unable to open the agent scheme: {detail}")
    return 0


def configure(args: argparse.Namespace) -> None:
    username = normalize_username(
        args.username
        or (args.app_config.username if args.app_config and args.app_config.username else "")
        or (input("TopSAG username: ").strip() if sys.stdin.isatty() else "")
    )
    password = os.environ.get(args.password_env) or ""
    if not password:
        if not sys.stdin.isatty():
            raise LauncherError(
                f"Password not set. Export {args.password_env} or run --configure in a terminal."
            )
        password = getpass.getpass("TopSAG password: ")
    if not password:
        raise LauncherError("Password cannot be empty.")
    account = credential_account(args, username)
    keychain_set(PASSWORD_SERVICE, password, account)
    config = args.app_config or AppConfig(base_url=args.base_url)
    config.base_url = args.base_url
    config.username = username
    if _argv_has("--insecure"):
        config.insecure = True
    if not config.hosts:
        config.hosts = [HostConfig(name="web", protocol="SSH")]
    write_config(config)
    print(f"Saved config to {config_path()}")
    print("Saved password to macOS Keychain.")


def run_from_stdin(args: argparse.Namespace) -> SessionState:
    return read_session_stdin()


def main() -> int:
    try:
        args = parse_args()
    except (LauncherError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.insecure:
        requests.packages.urllib3.disable_warnings(  # type: ignore[attr-defined]
            requests.packages.urllib3.exceptions.InsecureRequestWarning  # type: ignore[attr-defined]
        )

    try:
        if args.write_hosts_file:
            if args.app_config is None:
                raise LauncherError("config.toml is required to write the hosts file.")
            write_hosts_file(args.app_config)
            print(hosts_path())
            return 0
        if args.configure:
            configure(args)
            return 0

        session = make_session(args)
        if args.token_stdin:
            state = run_from_stdin(args)
            username = normalize_username(
                str(state.user_info.get("userName") or args.username or "diagnostic@default")
            )
        else:
            username = get_username(args)
            if args.forget_session:
                keychain_delete(SESSION_SERVICE, credential_account(args, username))
            state = load_cached_session(args, username)
            if state is None:
                print("No cached session; logging in.", file=sys.stderr)
                password = get_password(args, username)
                state = login(session, args, username, password)

        try:
            response, asset_payload = list_assets(session, args, state)
        except AuthExpired:
            if args.token_stdin:
                raise
            print("Cached session expired; logging in again.", file=sys.stderr)
            password = get_password(args, username)
            state = login(session, args, username, password)
            response, asset_payload = list_assets(session, args, state)

        refreshed_token = response.headers.get("token")
        if refreshed_token:
            state = SessionState(refreshed_token, state.user_info, state.company_alias)
        if not args.no_cache_session and not args.token_stdin:
            save_cached_session(args, state, username)

        target = select_target(args, asset_payload)
        scheme, details = build_agent_scheme(session, args, state, target)

        if args.print_scheme:
            print(scheme)
        else:
            print(
                "Fresh session created: "
                f"{details['assetName']} ({details['assetIp']}) "
                f"{details['account']}/{details['protocol']}:{details['assetPort']} "
                f"via {details['client']}",
                file=sys.stderr if args.remote_command else sys.stdout,
            )

        if not args.no_launch:
            status = launch_scheme(scheme, args, state)
            if args.remote_command and status == 255:
                time.sleep(0.4)
                scheme, details = build_agent_scheme(session, args, state, target)
                print(
                    "Remote SSH session dropped; retrying once with a fresh session.",
                    file=sys.stderr,
                )
                if args.print_scheme:
                    print(scheme)
                else:
                    print(
                        "Fresh session created: "
                        f"{details['assetName']} ({details['assetIp']}) "
                        f"{details['account']}/{details['protocol']}:{details['assetPort']} "
                        f"via {details['client']}",
                        file=sys.stderr,
                    )
                status = launch_scheme(scheme, args, state)
            return status
        return 0
    except (LauncherError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
