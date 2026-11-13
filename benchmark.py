"""
Benchmark theo Experimental Design mục 5 -> raw_measurements.csv (540 dòng) + config.json
Task 3 Implementation. Chỉ đo đúng lời gọi encrypt()/decrypt(); chuẩn bị key, cipher, nonce,
kiểm tra kết quả và ghi CSV đều nằm ngoài vùng đo.

Chạy: python benchmark.py --manifest dataset_manifest.csv --session S01
      python benchmark.py --session S02 --warmup 5 --runs 30   (giá trị mặc định)
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time

from crypto_core import (ALGORITHM_NAMES, NONCE_SIZE, TAG_SIZE, NonceCounter,
                         make_cipher, new_key)

DEFAULT_WARMUP, DEFAULT_RUNS = 5, 30
ALGS = ALGORITHM_NAMES
DATASET_ORDER = ["TXT01", "TXT05", "TXT10", "IMG01", "IMG05", "IMG10", "BIN01", "BIN05", "BIN10"]
FIELDS = ["session_id", "protocol_version", "scenario_id", "algorithm", "dataset_id", "data_type",
          "actual_size_bytes", "run_index", "execution_order", "enc_ns", "dec_ns",
          "api_output_bytes", "package_bytes", "overhead_bytes", "roundtrip_ok"]


def load_manifest(path):
    base = os.path.dirname(os.path.abspath(path))
    with open(path, newline="", encoding="utf-8") as f:
        rows = {r["dataset_id"]: r for r in csv.DictReader(f)}
    out = []
    for ds in DATASET_ORDER:
        r = rows[ds]
        with open(os.path.join(base, r["filename"]), "rb") as f:
            data = f.read()
        if hashlib.sha256(data).hexdigest() != r["sha256"].lower():
            sys.exit(f"{ds}: SHA-256 mismatch")
        out.append((ds, r["data_type"], data))
    return out


def require_row_count(actual, expected):
    if actual != expected:
        raise SystemExit(f"ERROR: {actual} rows produced, expected {expected}")


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="dataset_manifest.csv")
    ap.add_argument("--session", required=True)
    ap.add_argument("--protocol", default="v1")
    ap.add_argument("--out", default="raw_measurements.csv")
    ap.add_argument("--warmup", type=positive_int, default=DEFAULT_WARMUP,
                    help=f"unmeasured warm-up pairs per scenario (default {DEFAULT_WARMUP})")
    ap.add_argument("--runs", type=positive_int, default=DEFAULT_RUNS,
                    help=f"measured pairs per scenario (default {DEFAULT_RUNS})")
    args = ap.parse_args()

    datasets = load_manifest(args.manifest)
    rows = []
    for ds_id, dtype, data in datasets:
        B = len(data)
        # Chuẩn bị ngoài vùng đo: key mới cho từng scenario, cipher object, nonce counter
        state = {}
        for name in ALGS:
            state[name] = (make_cipher(name, new_key()), NonceCounter())

        # Warm-up không đo (vẫn tiêu thụ nonce)
        for name in ALGS:
            cipher, ctr = state[name]
            for _ in range(args.warmup):
                n = ctr.next()
                cipher.decrypt(n, cipher.encrypt(n, data, None), None)

        # Các vòng đo; vòng lẻ AES trước, vòng chẵn ChaCha20 trước
        for run in range(1, args.runs + 1):
            order = ALGS if run % 2 == 1 else ALGS[::-1]
            for pos, name in enumerate(order, start=1):
                cipher, ctr = state[name]
                nonce = ctr.next()                       # cấp nonce trước khi đo
                t0 = time.perf_counter_ns()
                out = cipher.encrypt(nonce, data, None)
                t1 = time.perf_counter_ns()
                t2 = time.perf_counter_ns()
                pt = cipher.decrypt(nonce, out, None)
                t3 = time.perf_counter_ns()
                ok = pt == data                          # kiểm tra ngoài vùng đo
                if not ok:
                    sys.exit(f"Round-trip FAILED: {name} {ds_id} run {run}")
                package = NONCE_SIZE + len(out)
                rows.append(dict(
                    session_id=args.session, protocol_version=args.protocol,
                    scenario_id=f"{name}|{ds_id}", algorithm=name, dataset_id=ds_id,
                    data_type=dtype, actual_size_bytes=B, run_index=run, execution_order=pos,
                    enc_ns=t1 - t0, dec_ns=t3 - t2, api_output_bytes=len(out),
                    package_bytes=package, overhead_bytes=package - B, roundtrip_ok=ok))
        print(f"{ds_id} done")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    config = {
        "session_id": args.session, "protocol_version": args.protocol,
        "algorithms": {"AES-256-GCM": "AESGCM", "ChaCha20-Poly1305": "ChaCha20Poly1305"},
        "key_bits": 256, "nonce_policy_check": "counters never reset within a scenario", "nonce_bytes": NONCE_SIZE, "tag_bytes": TAG_SIZE, "aad": None,
        "units": "1 MB = 1,000,000 bytes; time in ns",
        "dataset_order": DATASET_ORDER, "warmup_pairs": args.warmup, "measured_pairs": args.runs,
        "nonce_policy": "fresh key per scenario; 12-byte big-endian counter incl. warm-ups",
        "execution_order": "odd rounds AES first, even rounds ChaCha20 first",
        "timing_boundary": "only encrypt()/decrypt() API calls, perf_counter_ns",
        "output_package": "nonce || ciphertext || tag",
    }
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    expected_rows = len(datasets) * len(ALGS) * args.runs
    print(f"{len(rows)} rows -> {args.out} (expected {expected_rows}: "
          f"{len(datasets)} datasets x {len(ALGS)} algorithms x {args.runs} runs)")
    require_row_count(len(rows), expected_rows)


if __name__ == "__main__":
    main()
