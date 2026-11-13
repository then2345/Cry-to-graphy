"""
Ghi thông tin máy chạy benchmark -> environment.json  (Experimental Design, mục 2)
Chạy: pip install py-cpuinfo   (khuyến nghị, để đọc tên CPU + AES-NI trên Windows/macOS)
      python collect_env.py --session S01

Sau khi commit/push, chỉ cập nhật source_revision mà không đổi thông số môi trường:
      python collect_env.py --update-revision-only
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime

import cryptography
from cryptography.hazmat.backends.openssl.backend import backend

SOURCE_FILES = [
    "crypto_core.py",
    "make_datasets.py",
    "benchmark.py",
    "collect_env.py",
    "functional_tests.py",
    "analyze.py",
    "flow_diagram.py",
    "run_all.py",
    "requirements.txt",
    "README.md",
]


def cpu_info():
    name, flags = platform.processor() or "unknown", None
    try:
        import cpuinfo  # py-cpuinfo
        info = cpuinfo.get_cpu_info()
        name = info.get("brand_raw", name)
        flags = set(info.get("flags", []))
    except ImportError:
        try:  # Linux fallback
            with open("/proc/cpuinfo") as f:
                txt = f.read()
            for line in txt.splitlines():
                if line.startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                if line.startswith("flags") or line.startswith("Features"):
                    flags = set(line.split(":", 1)[1].split())
                    break
        except OSError:
            pass
    if flags is None:
        aes = "unknown"
    else:
        aes = "yes" if "aes" in flags else "no"
    return name, aes


def ram_gb():
    try:
        import psutil
        return round(psutil.virtual_memory().total / 1e9, 1)
    except ImportError:
        try:
            with open("/proc/meminfo") as f:
                return round(int(f.readline().split()[1]) * 1024 / 1e9, 1)
        except OSError:
            return "unknown (pip install psutil)"


def git_revision():
    """Return (commit, dirty) or (None, False) when not in a git repo."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        ).strip())
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, False


def content_revision():
    """Fallback source fingerprint when git is unavailable."""
    h = hashlib.sha256()
    for name in SOURCE_FILES:
        if os.path.exists(name):
            h.update(name.encode("utf-8"))
            with open(name, "rb") as f:
                h.update(f.read())
    return "sha256:" + h.hexdigest()


def resolve_revision(revision):
    """Return (source_revision, source_revision_type, source_dirty)."""
    if revision and revision != "TO RECORD":
        return revision, "manual", None
    commit, dirty = git_revision()
    if commit:
        return commit, "git", dirty
    return content_revision(), "content-hash", None


def update_revision_only(revision):
    path = "environment.json"
    if not os.path.exists(path):
        sys.exit(f"{path} not found; run the full pipeline first")
    with open(path, encoding="utf-8") as f:
        env = json.load(f)
    rev, kind, dirty = resolve_revision(revision)
    env["source_revision"] = rev
    env["source_revision_type"] = kind
    env["source_dirty"] = dirty
    with open(path, "w", encoding="utf-8") as f:
        json.dump(env, f, indent=2, ensure_ascii=False)
    print(f"source_revision updated: {rev} ({kind})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="session id, vd S01")
    ap.add_argument("--protocol", default="v1")
    ap.add_argument("--power", default="TO RECORD", help='vd: "plugged-in, best performance"')
    ap.add_argument("--revision", default=None,
                    help="git commit/version; mặc định tự detect git, fallback SHA-256 source")
    ap.add_argument("--update-revision-only", action="store_true",
                    help="chỉ cập nhật source_revision trong environment.json hiện có")
    args = ap.parse_args()

    if args.update_revision_only:
        update_revision_only(args.revision)
        return
    if not args.session:
        ap.error("--session is required unless --update-revision-only is used")

    cpu, aes = cpu_info()
    clk = time.get_clock_info("perf_counter")
    revision, revision_type, dirty = resolve_revision(args.revision)
    env = {
        "session_id": args.session,
        "protocol_version": args.protocol,
        "date": datetime.now().isoformat(timespec="seconds"),
        "cpu": cpu,
        "architecture": platform.machine(),
        "aes_hardware_support": aes,
        "ram_gb": ram_gb(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": sys.version.split()[0],
        "cryptography": cryptography.__version__,
        "openssl": backend.openssl_version_text(),
        "timer": "time.perf_counter_ns",
        "timer_resolution_s": clk.resolution,
        "power_conditions": args.power,
        "source_revision": revision,
        "source_revision_type": revision_type,
        "source_dirty": dirty,
        "execution": "native (edit if running in a VM)",
    }
    with open("environment.json", "w", encoding="utf-8") as f:
        json.dump(env, f, indent=2, ensure_ascii=False)
    for k, v in env.items():
        print(f"{k:22}: {v}")


if __name__ == "__main__":
    main()
