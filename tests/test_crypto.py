#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(ROOT))

from crypto import (  # noqa: E402
    AES_KEY,
    aes_decrypt,
    aes_encrypt,
    base_aes_decrypt,
    base_aes_encrypt,
    compact_json,
    pad_nul,
    parse_agent_scheme,
)


class CryptoTests(unittest.TestCase):
    def test_roundtrip(self):
        payload = compact_json({"alias": "default", "sessionId": "abc", "hello": "世界"})
        encoded = base_aes_encrypt(payload)
        self.assertEqual(base_aes_decrypt(encoded), payload)

    def test_scheme_parse(self):
        body = {"alias": "default", "sessionId": "s1", "serverIp": "10.0.0.1"}
        scheme = "agent://command&" + base_aes_encrypt(compact_json(body)) + "&"
        parsed = parse_agent_scheme(scheme)
        self.assertEqual(parsed["serverIp"], "10.0.0.1")

    def test_matches_cryptography_if_present(self):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        except ImportError:
            self.skipTest("cryptography is not installed")
        data = pad_nul(b'{"k":"v"}')
        ref = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_KEY)).encryptor()
        expected = ref.update(data) + ref.finalize()
        self.assertEqual(aes_encrypt(data, AES_KEY), expected)
        self.assertEqual(aes_decrypt(expected, AES_KEY).rstrip(b"\x00"), b'{"k":"v"}')


if __name__ == "__main__":
    unittest.main()
