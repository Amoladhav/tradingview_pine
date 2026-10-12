"""Verify isolation before trusting synthetic application tests."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest

import offline_boundary


class OfflineBoundaryTests(unittest.TestCase):
    def test_network_and_processes_are_denied(self):
        with self.assertRaises(PermissionError):
            socket.socket()
        with self.assertRaises(PermissionError):
            subprocess.run([sys.executable, "-c", "pass"], check=True)

    def test_real_user_paths_are_denied(self):
        with self.assertRaises(PermissionError):
            Path("/outside-offline-boundary/credentials").read_text()

    def test_environment_is_synthetic(self):
        self.assertEqual(Path(os.environ["HOME"]), offline_boundary.temp)
        self.assertEqual(Path.cwd(), offline_boundary.temp)
        self.assertNotIn("TRADIER_TOKEN", os.environ)
        self.assertNotIn("TRADIER_SANDBOX_TOKEN", os.environ)

    def test_writes_outside_temp_are_denied(self):
        with self.assertRaises(PermissionError):
            (Path(__file__).parent / "must_not_exist.txt").write_text("synthetic")


if __name__ == "__main__":
    unittest.main()
