#!/usr/bin/env python3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(ROOT))

import topsag_ssh as app  # noqa: E402
from crypto import base_aes_encrypt, compact_json  # noqa: E402

payload = {
    "alias": "default",
    "sessionId": "test",
    "serverIp": "127.0.0.1",
    "serverPort": "22",
    "serverPwd": "expected-secret",
    "protocol": "SSH",
}
app.terminal_ssh_command = lambda value: (
    [
        "/bin/sh",
        "-c",
        'printf "password: "; IFS= read -r supplied; '
        'test "$supplied" = "expected-secret" && echo TOPSAG_PASSWORD_OK',
    ],
    payload["serverPwd"],
)
scheme = "agent://command&" + base_aes_encrypt(compact_json(payload)) + "&"
args = SimpleNamespace(base_url="https://bastion.example.com", timeout=5, insecure=True, remote_command=None)
state = app.SessionState(token="test-token", user_info={"userName": "test@default"}, company_alias="default")
observed = {"keepalive_started": threading.Event()}


def fake_keepalive(received_args, received_state, stop_event):
    observed["args"] = received_args
    observed["state"] = received_state
    observed["stop_event"] = stop_event
    observed["keepalive_started"].set()
    stop_event.wait(5)


def fake_run(*_args, **_kwargs):
    if not observed["keepalive_started"].wait(1):
        raise AssertionError("Web keepalive thread did not start")
    return app.subprocess.CompletedProcess([], 0)


fake_sys = SimpleNamespace(
    stdin=SimpleNamespace(isatty=lambda: True),
    stdout=SimpleNamespace(isatty=lambda: True),
    stderr=sys.stderr,
    platform="darwin",
)
app.sys = fake_sys
app.keep_web_session_alive = fake_keepalive
app.subprocess.run = fake_run
app.ping_web_keepalive = lambda *a, **k: True
exit_status = app.launch_scheme_in_current_terminal(scheme, args, state)
assert observed["args"] is args
assert observed["state"] is state
assert observed["stop_event"].is_set()
assert exit_status == 0
print("TERMINAL_LAUNCH_KEEPALIVE_OK")
