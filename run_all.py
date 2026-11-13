"""
Chạy toàn bộ Task 4 một lần:
    python run_all.py --session S01 --power "plugged-in, best performance"

Nếu chưa có dataset_manifest.csv thì tạo 9 input bằng make_datasets.py (spec mục 3).
Lần sau chạy lại sẽ dùng lại đúng các file đó (binary không bị sinh lại).
Nếu truyền --seed, toàn bộ dataset được sinh lại bằng --force --seed.
"""
import argparse
import os
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--session", required=True)
ap.add_argument("--protocol", default="v1")
ap.add_argument("--power", default="TO RECORD")
ap.add_argument("--revision", default=None,
                help="git commit/version; mặc định collect_env.py tự detect")
ap.add_argument("--seed", type=int, default=None,
                help="seed cho BIN deterministic; sinh lại toàn bộ dataset với --force")
a = ap.parse_args()


def run(*cmd):
    print("\n>>>", " ".join(cmd))
    subprocess.run([sys.executable, *cmd], check=True)


if a.seed is not None:
    print("NOTE: --seed regenerates all datasets with --force.")
    run("make_datasets.py", "--force", "--seed", str(a.seed))
elif not os.path.exists("dataset_manifest.csv"):
    run("make_datasets.py")

env_cmd = ["collect_env.py", "--session", a.session, "--protocol", a.protocol, "--power", a.power]
if a.revision:
    env_cmd += ["--revision", a.revision]
run(*env_cmd)
run("functional_tests.py", "--session", a.session, "--protocol", a.protocol)  # dừng nếu không 90/90
run("benchmark.py", "--session", a.session, "--protocol", a.protocol)
run("analyze.py")
run("flow_diagram.py")
print("\nDONE. Gửi cho người viết report: environment.json, summary.csv, functional_tests.csv,"
      " fig_latency.png, fig_throughput.png, fig_flow.png")
