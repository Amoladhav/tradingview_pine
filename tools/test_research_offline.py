"""Run reviewed synthetic research tests without provider or credential access.

Usage: .venv/bin/python -I -S tools/test_research_offline.py
This Python audit boundary is not a sandbox for hostile native extensions.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--deps", type=Path)
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    dependencies = args.deps
    if dependencies is None:
        # -S skips venv site initialization; locate packages beside the executable.
        prefix = Path(sys.executable).absolute().parent.parent
        dependencies = prefix / ("Lib/site-packages" if os.name == "nt" else
                                 f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
    dependencies = dependencies.resolve()
    if not dependencies.is_dir():
        parser.error("Use the virtual-environment interpreter or --deps SITE_PACKAGES")
    if args.child is None:
        with tempfile.TemporaryDirectory(prefix="research-offline-") as directory:
            environment = {"HOME": directory, "USERPROFILE": directory,
                           "TMPDIR": directory, "TMP": directory, "TEMP": directory,
                           "PATH": str(Path(sys.executable).parent),
                           "OPENBLAS_NUM_THREADS": "1", "OPENBLAS_MAIN_FREE": "1",
                           "OMP_NUM_THREADS": "1"}
            if os.name == "nt":
                environment["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
            return subprocess.run(
                [sys.executable, "-I", "-S", str(Path(__file__).resolve()),
                 "--child", directory, "--deps", str(dependencies), "--pattern", args.pattern],
                cwd=directory, env=environment, check=False,
            ).returncode

    scratch = args.child.resolve()
    stdlib = Path(os.__file__).resolve().parent
    read_roots = (stdlib, dependencies, ROOT / "python_scritps", ROOT / "tests",
                  ROOT / "range_collector", ROOT / "intraday_collector", scratch,
                  Path("/usr/share/zoneinfo"))
    read_files = {ROOT / "pyproject.toml", ROOT / "requirements.txt",
                  ROOT / "docs" / "RSI_STUDY.md", Path("/etc/localtime").resolve()}

    def allowed(path: Path, roots: tuple[Path, ...]) -> bool:
        return any(path == root or root in path.parents for root in roots)

    def guard(event: str, values: tuple) -> None:
        if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn")) or event in {
            "os.system", "os.fork", "os.forkpty", "os.putenv", "os.unsetenv",
        }:
            raise PermissionError("OFFLINE_OPERATION_DENIED")
        if event == "open" and isinstance(values[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(values[0])).resolve()
            writing = bool(values[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            permitted = allowed(path, (scratch,)) if writing else (
                allowed(path, read_roots) or path in read_files)
            if not permitted:
                raise PermissionError("OFFLINE_FILE_DENIED")
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.rename", "os.link", "os.symlink"}:
            paths = values[:2] if event in {"os.rename", "os.link", "os.symlink"} else values[:1]
            for raw in paths:
                if not isinstance(raw, (str, bytes, os.PathLike)) or not allowed(
                    Path(os.fsdecode(raw)).resolve(), (scratch,)
                ):
                    raise PermissionError("OFFLINE_WRITE_DENIED")

    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT / "python_scritps"), str(ROOT), str(dependencies)]
    sys.addaudithook(guard)
    # No .pth files or sitecustomize are executed. Environment and HOME belong
    # exclusively to this synthetic subprocess, including native-library reads.
    import types
    boundary = types.ModuleType("offline_boundary")
    boundary.temp = scratch
    boundary.guard = guard
    sys.modules["offline_boundary"] = boundary
    import unittest
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=args.pattern)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
