#!/usr/bin/env python3
import argparse
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(ROOT))

import topsag_ssh as app  # noqa: E402


def payload():
    return {
        "data": {
            "list": [
                {
                    "assetName": "web-prod",
                    "assetIp": "10.0.0.8",
                    "account": [
                        {"protocol": "SSH", "account": "root", "authType": "0"},
                        {"protocol": "SFTP", "account": "root", "authType": "0"},
                    ],
                    "protocols": [
                        {"name": "SSH", "port": 22},
                        {"name": "SFTP", "port": 22},
                    ],
                },
                {
                    "assetName": "db-prod",
                    "assetIp": "10.0.0.9",
                    "account": [{"protocol": "SSH", "account": "ops", "authType": "0"}],
                    "protocols": [{"name": "SSH", "port": 22}],
                },
            ]
        }
    }


class SelectTargetTests(unittest.TestCase):
    def test_index(self):
        args = SimpleNamespace(asset_name="", asset_index=1, account_index=0, protocol="SSH")
        target = app.select_target(args, payload())
        self.assertEqual(target.asset["assetName"], "db-prod")

    def test_asset_name(self):
        args = SimpleNamespace(asset_name="web-prod", asset_index=0, account_index=0, protocol="SSH")
        target = app.select_target(args, payload())
        self.assertEqual(target.asset["assetIp"], "10.0.0.8")
        self.assertEqual(target.account["protocol"], "SSH")

    def test_missing_name(self):
        args = SimpleNamespace(asset_name="nope", asset_index=0, account_index=0, protocol="SSH")
        with self.assertRaises(app.LauncherError):
            app.select_target(args, payload())


if __name__ == "__main__":
    unittest.main()
