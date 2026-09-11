#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(ROOT))

from config import AppConfig, ConfigError, HostConfig, load_config, write_config  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            config = AppConfig(
                base_url="https://bastion.example.com",
                username="alice@default",
                insecure=True,
                hosts=[
                    HostConfig(name="web", asset_index=0, protocol="SSH"),
                    HostConfig(name="db", asset_index=2, asset_name="pg-1"),
                ],
            )
            write_config(config, path)
            loaded = load_config(path)
            self.assertEqual(loaded.base_url, "https://bastion.example.com")
            self.assertTrue(loaded.insecure)
            self.assertEqual([host.name for host in loaded.hosts], ["web", "db"])
            self.assertEqual(loaded.host_named("db").asset_name, "pg-1")
            hosts_file = Path(tmp) / "hosts"
            # write_config uses default hosts_path unless env is set; check file body instead
            text = path.read_text()
            self.assertIn("[[hosts]]", text)
            self.assertNotIn("internal.example", text)

    def test_missing_base_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text("username = \"alice@default\"\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_duplicate_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                "base_url = \"https://bastion.example.com\"\n"
                "[[hosts]]\nname = \"web\"\n"
                "[[hosts]]\nname = \"web\"\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
