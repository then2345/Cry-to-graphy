"""
Task 4 - Functional tests (Experimental Design, section 4)
AES-256-GCM vs ChaCha20-Poly1305

- 5 required tests (T1-T5) x 2 algorithms x 9 datasets = 90 rows
- Separate test keys, AAD = None, run outside benchmark timing
- Output: functional_tests.csv (schema from section 4)

Usage:
    pip install cryptography
    python functional_tests.py --manifest dataset_manifest.csv --session S01 --protocol v1
The manifest is produced by Task 3 (columns: dataset_id, data_type, target_size_bytes,
actual_size_bytes, filename, sha256, generation_method). `filename` is resolved
relative to the manifest's folder.
"""
import argparse
import csv
import hashlib
import os
import sys

from crypto_core import ALGORITHMS, KEY_SIZE, NONCE_SIZE, TAG_SIZE, InvalidTag
DATASET_ORDER = ["TXT01", "TXT05", "TXT10", "IMG01", "IMG05", "IMG10", "BIN01", "BIN05", "BIN10"]
FIELDS = ["session_id", "protocol_version", "algorithm", "dataset_id", "test_id",
          "expected_result", "actual_result", "status", "exception_type", "notes"]


def flip_bit(data: bytes, index: int) -> bytes:
    b = bytearray(data)
    b[index] ^= 0x01
    return bytes(b)


def load_datasets(manifest_path):
    base = os.path.dirname(os.path.abspath(manifest_path))
    with open(manifest_path, newline="", encoding="utf-8") as f:
        rows = {r["dataset_id"]: r for r in csv.DictReader(f)}
    missing = [d for d in DATASET_ORDER if d not in rows]
    if missing:
        sys.exit(f"Manifest is missing datasets: {missing}")
    datasets = {}
    for ds_id in DATASET_ORDER:
        r = rows[ds_id]
        with open(os.path.join(base, r["filename"]), "rb") as f:
            data = f.read()
        if len(data) != int(r["actual_size_bytes"]):
            sys.exit(f"{ds_id}: size {len(data)} != manifest {r['actual_size_bytes']}")
        if hashlib.sha256(data).hexdigest() != r["sha256"].lower():
            sys.exit(f"{ds_id}: SHA-256 does not match manifest")
        datasets[ds_id] = data
    return datasets


def negative_test(cls, key, nonce, buf):
    """Expect InvalidTag. Returns (actual_result, status, exception_type, notes)."""
    try:
        cls(key).decrypt(nonce, buf, None)
        return "ACCEPTED", "FAIL", "", "modified input was accepted"
    except InvalidTag:
        return "InvalidTag", "PASS", "", ""
    except Exception as e:  # any other exception is a FAIL, not a rejection
        return "EXCEPTION", "FAIL", type(e).__name__, str(e)


def run_scenario(alg, cls, ds_id, plaintext):
    key = os.urandom(KEY_SIZE)      # separate test key, not a benchmark key
    nonce = os.urandom(NONCE_SIZE)
    out = cls(key).encrypt(nonce, plaintext, None)   # ciphertext || tag
    assert len(out) == len(plaintext) + TAG_SIZE

    results = []
    # T1 Round trip
    try:
        pt = cls(key).decrypt(nonce, out, None)
        ok = pt == plaintext
        results.append(("T1", "Plaintext identical",
                        "Plaintext identical" if ok else "Plaintext mismatch",
                        "PASS" if ok else "FAIL", "", ""))
    except Exception as e:
        results.append(("T1", "Plaintext identical", "EXCEPTION", "FAIL", type(e).__name__, str(e)))

    expected = "InvalidTag"
    # T2 Wrong key: flip 1 bit of the key
    results.append(("T2", expected, *negative_test(cls, flip_bit(key, 0), nonce, out)))
    # T3 Wrong nonce: flip 1 bit of the nonce (length unchanged)
    results.append(("T3", expected, *negative_test(cls, key, flip_bit(nonce, 0), out)))
    # T4 Altered ciphertext: flip 1 bit in first ciphertext byte, tag unchanged
    results.append(("T4", expected, *negative_test(cls, key, nonce, flip_bit(out, 0))))
    # T5 Altered tag: flip 1 bit in final tag byte
    results.append(("T5", expected, *negative_test(cls, key, nonce, flip_bit(out, len(out) - 1))))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="dataset_manifest.csv")
    ap.add_argument("--session", required=True)
    ap.add_argument("--protocol", default="v1")
    ap.add_argument("--out", default="functional_tests.csv")
    args = ap.parse_args()

    datasets = load_datasets(args.manifest)
    rows = []
    for ds_id in DATASET_ORDER:
        for alg, cls in ALGORITHMS.items():
            for test_id, exp, act, status, exc, notes in run_scenario(alg, cls, ds_id, datasets[ds_id]):
                rows.append(dict(session_id=args.session, protocol_version=args.protocol,
                                 algorithm=alg, dataset_id=ds_id, test_id=test_id,
                                 expected_result=exp, actual_result=act, status=status,
                                 exception_type=exc, notes=notes))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    n_pass = sum(r["status"] == "PASS" for r in rows)
    print(f"{len(rows)} rows written to {args.out}: {n_pass} PASS, {len(rows) - n_pass} FAIL")
    if len(rows) != 90 or n_pass != 90:
        print("WARNING: required 90/90 PASS not met - do not start the official benchmark.")
        sys.exit(1)


if __name__ == "__main__":
    main()
