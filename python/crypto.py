"""AES-128 helpers for TopSAG agent:// payloads.

The algorithm, key, IV, NUL padding, and double-base64 wrapping match the
vendor Windows client (Call.exe / CallAgent.jar). They are protocol constants,
not deployment secrets.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict

AES_KEY = b"6a3c2dd76f53e69b"
LEGACY_FALLBACK_PASSWORD = "frp8fhf8nfr@fmy.GQH"

_SBOX = bytes(
    [
        0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
        0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
        0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
        0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
        0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
        0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
        0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
        0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
        0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
        0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
        0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
        0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
        0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
        0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
        0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
        0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
    ]
)
_INV_SBOX = bytes(_SBOX.index(i) for i in range(256))
_RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


class CryptoError(ValueError):
    pass


def _xtime(value: int) -> int:
    return ((value << 1) ^ 0x1B) & 0xFF if value & 0x80 else (value << 1) & 0xFF


def _expand_key(key: bytes) -> list[int]:
    if len(key) != 16:
        raise CryptoError("AES-128 requires a 16-byte key.")
    words = list(key)
    for index in range(16, 176, 4):
        temp = words[index - 4 : index]
        if index % 16 == 0:
            temp = [
                _SBOX[temp[1]] ^ _RCON[index // 16],
                _SBOX[temp[2]],
                _SBOX[temp[3]],
                _SBOX[temp[0]],
            ]
        words.extend(left ^ right for left, right in zip(words[index - 16 : index - 12], temp))
    return words


def _mix_column(column: list[int], invert: bool = False) -> None:
    a, b, c, d = column
    if invert:
        def multiply(value: int, factor: int) -> int:
            result = 0
            current = value
            while factor:
                if factor & 1:
                    result ^= current
                current = _xtime(current)
                factor >>= 1
            return result

        column[0] = multiply(a, 14) ^ multiply(b, 11) ^ multiply(c, 13) ^ multiply(d, 9)
        column[1] = multiply(a, 9) ^ multiply(b, 14) ^ multiply(c, 11) ^ multiply(d, 13)
        column[2] = multiply(a, 13) ^ multiply(b, 9) ^ multiply(c, 14) ^ multiply(d, 11)
        column[3] = multiply(a, 11) ^ multiply(b, 13) ^ multiply(c, 9) ^ multiply(d, 14)
        return
    column[0] = _xtime(a) ^ _xtime(b) ^ b ^ c ^ d
    column[1] = a ^ _xtime(b) ^ _xtime(c) ^ c ^ d
    column[2] = a ^ b ^ _xtime(c) ^ _xtime(d) ^ d
    column[3] = _xtime(a) ^ a ^ b ^ c ^ _xtime(d)


def _crypt_block(block: bytearray, round_keys: list[int], decrypt: bool) -> None:
    state = [block[row + 4 * column] for row in range(4) for column in range(4)]

    def add_round_key(round_index: int) -> None:
        offset = round_index * 16
        for index in range(16):
            state[index] ^= round_keys[offset + (index % 4) * 4 + (index // 4)]

    def shift_rows(invert: bool) -> None:
        for row in range(1, 4):
            start = 4 * row
            row_values = state[start : start + 4]
            shift = -row if invert else row
            state[start : start + 4] = row_values[shift:] + row_values[:shift]

    def sub_bytes(table: bytes) -> None:
        for index, value in enumerate(state):
            state[index] = table[value]

    def mix_columns(invert: bool) -> None:
        for column in range(4):
            values = [state[row * 4 + column] for row in range(4)]
            _mix_column(values, invert)
            for row in range(4):
                state[row * 4 + column] = values[row]

    if decrypt:
        add_round_key(10)
        for round_index in range(9, 0, -1):
            shift_rows(True)
            sub_bytes(_INV_SBOX)
            add_round_key(round_index)
            mix_columns(True)
        shift_rows(True)
        sub_bytes(_INV_SBOX)
        add_round_key(0)
    else:
        add_round_key(0)
        for round_index in range(1, 10):
            sub_bytes(_SBOX)
            shift_rows(False)
            mix_columns(False)
            add_round_key(round_index)
        sub_bytes(_SBOX)
        shift_rows(False)
        add_round_key(10)

    for row in range(4):
        for column in range(4):
            block[row + 4 * column] = state[row * 4 + column]


def aes_encrypt(data: bytes, key: bytes) -> bytes:
    if len(data) % 16:
        raise CryptoError("Plaintext must be padded to a 16-byte boundary.")
    round_keys = _expand_key(key)
    previous = key
    output = bytearray()
    for offset in range(0, len(data), 16):
        block = bytearray(left ^ right for left, right in zip(data[offset : offset + 16], previous))
        _crypt_block(block, round_keys, False)
        output.extend(block)
        previous = bytes(block)
    return bytes(output)


def aes_decrypt(data: bytes, key: bytes) -> bytes:
    if len(data) % 16:
        raise CryptoError("Ciphertext length must be a multiple of 16 bytes.")
    round_keys = _expand_key(key)
    previous = key
    output = bytearray()
    for offset in range(0, len(data), 16):
        block = bytearray(data[offset : offset + 16])
        current = bytes(block)
        _crypt_block(block, round_keys, True)
        output.extend(left ^ right for left, right in zip(block, previous))
        previous = current
    return bytes(output)


def pad_nul(data: bytes) -> bytes:
    remainder = len(data) % 16
    if remainder:
        data += b"\x00" * (16 - remainder)
    return data


def base_aes_encrypt(plain_text: str, key: bytes = AES_KEY) -> str:
    cipher_text = aes_encrypt(pad_nul(plain_text.encode("utf-8")), key)
    inner_base64 = base64.b64encode(cipher_text).decode("ascii")
    return base64.b64encode(inner_base64.encode("ascii")).decode("ascii")


def base_aes_decrypt(encoded: str, key: bytes = AES_KEY) -> str:
    try:
        inner_base64 = base64.b64decode(encoded).decode("ascii")
        cipher_text = base64.b64decode(inner_base64)
        plain_text = aes_decrypt(cipher_text, key)
        return plain_text.rstrip(b"\x00").decode("utf-8")
    except Exception as exc:
        raise CryptoError("Unable to decode the encrypted payload.") from exc


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_agent_scheme(scheme: str) -> Dict[str, Any]:
    prefix = "agent://command&"
    if not scheme.startswith(prefix):
        raise CryptoError("Unexpected agent scheme format.")
    encoded = scheme[len(prefix) :]
    if encoded.endswith("&"):
        encoded = encoded[:-1]
    try:
        payload = json.loads(base_aes_decrypt(encoded))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CryptoError("Unable to decode the agent scheme payload.") from exc
    if not isinstance(payload, dict):
        raise CryptoError("Agent scheme payload is not a JSON object.")
    return payload
