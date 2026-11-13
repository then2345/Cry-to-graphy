"""
Tự kiểm tra nhanh (stdlib unittest, không cần thêm dependency):

    python -m unittest -v test_metrics.py

Bao gồm:
  - round-trip và overhead 28 B của cả hai AEAD; tamper phải ném InvalidTag
  - NonceCounter: nonce 12 B, tăng dần, không lặp
  - công thức thống kê: mean, SD (ddof=1), median, CI 95%, throughput, overhead %
  - t critical: df=29 -> 2.045 (khớp giá trị đã dùng cho S01)
  - tính nhất quán của artifact hiện có (nếu đã chạy pipeline)
"""
import csv
import json
import math
import os
import unittest

import pandas as pd
from cryptography.exceptions import InvalidTag

import analyze
import benchmark
import make_datasets
from crypto_core import (ALGORITHM_NAMES, KEY_SIZE, NONCE_SIZE, TAG_SIZE,
                         NonceCounter, decrypt, encrypt, from_package,
                         make_cipher, new_key, to_package)


class CryptoCoreTests(unittest.TestCase):
    def test_roundtrip_and_package_overhead(self):
        msg = bytes(range(256)) * 40  # 10,240 B
        nonce = NonceCounter().next()
        for name in ALGORITHM_NAMES:
            with self.subTest(algorithm=name):
                cipher = make_cipher(name, new_key())
                out = encrypt(cipher, nonce, msg)
                self.assertEqual(len(out), len(msg) + TAG_SIZE)
                self.assertEqual(decrypt(cipher, nonce, out), msg)
                package = to_package(nonce, out)
                self.assertEqual(len(package), len(msg) + NONCE_SIZE + TAG_SIZE)
                self.assertEqual(len(package) - len(msg), 28)
                self.assertEqual(from_package(package), (nonce, out))

    def test_tampering_is_rejected(self):
        msg = b"Introduction to Cryptography benchmark. " * 10
        for name in ALGORITHM_NAMES:
            with self.subTest(algorithm=name):
                key = new_key()
                nonce = NonceCounter().next()
                out = encrypt(make_cipher(name, key), nonce, msg)
                flipped_ct = bytes([out[0] ^ 1]) + out[1:]
                flipped_tag = out[:-1] + bytes([out[-1] ^ 1])
                for wrong_key, wrong_nonce, buf in [
                    (bytes([key[0] ^ 1]) + key[1:], nonce, out),
                    (key, bytes([nonce[0] ^ 1]) + nonce[1:], out),
                    (key, nonce, flipped_ct),
                    (key, nonce, flipped_tag),
                ]:
                    with self.assertRaises(InvalidTag):
                        decrypt(make_cipher(name, wrong_key), wrong_nonce, buf)

    def test_nonce_counter(self):
        ctr = NonceCounter()
        nonces = [ctr.next() for _ in range(3)]
        self.assertEqual(len({len(n) for n in nonces}), 1)
        self.assertEqual(nonces[0], (1).to_bytes(NONCE_SIZE, "big"))
        self.assertEqual(int.from_bytes(nonces[2], "big"), 3)
        self.assertEqual(len(set(nonces)), 3)
        self.assertEqual(ctr.used, 3)
        self.assertEqual(KEY_SIZE, 32)


class StatisticsTests(unittest.TestCase):
    def test_t_critical(self):
        self.assertEqual(analyze.t_critical(29), 2.045)  # giá trị dùng cho S01
        self.assertEqual(analyze.t_critical(9), 2.262)
        self.assertEqual(analyze.t_critical(3), 3.182)
        self.assertEqual(analyze.t_critical(30), 2.042)
        self.assertGreater(analyze.t_critical(29), analyze.t_critical(120))

    def test_summarize_formulas(self):
        n, size = 4, 1_000_000
        enc = [1e6, 2e6, 3e6, 4e6]
        raw = pd.DataFrame({
            "session_id": ["S"] * n, "protocol_version": ["v1"] * n,
            "algorithm": [ALGORITHM_NAMES[0]] * n, "dataset_id": ["TXT01"] * n,
            "data_type": ["text"] * n, "actual_size_bytes": [size] * n,
            "enc_ns": enc, "dec_ns": [2e6] * n, "overhead_bytes": [28] * n,
        })
        s = analyze.summarize(raw).iloc[0]
        self.assertEqual(s["n"], n)
        self.assertAlmostEqual(s["enc_mean_ms"], 2.5)
        self.assertAlmostEqual(s["enc_sd_ms"], math.sqrt(5 / 3), places=12)
        self.assertAlmostEqual(s["enc_median_ms"], 2.5)
        self.assertAlmostEqual(s["enc_ci95_low_ms"], 2.5 - 3.182 * math.sqrt(5 / 3) / 2, places=12)
        self.assertAlmostEqual(s["enc_ci95_high_ms"], 2.5 + 3.182 * math.sqrt(5 / 3) / 2, places=12)
        # throughput = tổng byte / tổng thời gian, không phải trung bình các rate
        self.assertAlmostEqual(s["enc_MB_s"], 400.0)
        self.assertAlmostEqual(s["dec_MB_s"], 500.0)
        self.assertAlmostEqual(s["overhead_pct"], 100 * 28 / size)

    def test_require_row_count(self):
        benchmark.require_row_count(540, 540)
        with self.assertRaises(SystemExit):
            benchmark.require_row_count(539, 540)

    def test_validate_raw_rejects_wrong_run_count(self):
        incomplete = pd.DataFrame({
            "algorithm": ["AES-256-GCM"] * 2, "dataset_id": ["TXT01"] * 2,
        })
        with self.assertRaises(SystemExit):
            analyze.validate_raw(incomplete)

        complete = pd.DataFrame([
            {"algorithm": a, "dataset_id": d}
            for a in ALGORITHM_NAMES for d in analyze.DATASET_ORDER for _ in range(4)
        ])
        self.assertEqual(analyze.validate_raw(complete), 4)
        with self.assertRaises(SystemExit):
            analyze.validate_raw(complete, measured_pairs=5)


class DatasetTests(unittest.TestCase):
    def test_text_is_exact_size_and_ascii(self):
        data = make_datasets.make_text(1_000_000)
        self.assertEqual(len(data), 1_000_000)
        self.assertEqual(data[:len(make_datasets.SENTENCE)], make_datasets.SENTENCE)
        self.assertTrue(all(b < 128 for b in data[:5000]))

    def test_bmp_header_and_size(self):
        width, height = 4, 3
        data = make_datasets.make_bmp(width, height)
        self.assertEqual(len(data), make_datasets.BMP_HEADER + width * 3 * height)
        make_datasets.validate_bmp(data, width, height)


class ArtifactConsistencyTests(unittest.TestCase):
    """Kiểm tra bộ output hiện có khớp cấu hình; bỏ qua nếu chưa chạy pipeline."""

    def _require(self, path):
        if not os.path.exists(path):
            self.skipTest(f"{path} not found; run run_all.py first")
        return path

    def test_raw_and_summary_match_config(self):
        with open(self._require("config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        raw = pd.read_csv(self._require("raw_measurements.csv"))
        runs = analyze.validate_raw(raw, int(cfg["measured_pairs"]))
        self.assertEqual(len(raw), 18 * runs)
        s = pd.read_csv(self._require("summary.csv"))
        self.assertEqual(len(s), 18)
        self.assertTrue((s["n"] == runs).all())
        self.assertTrue((s["overhead_bytes"] == 28).all())

    def test_functional_tests_all_pass(self):
        with open(self._require("functional_tests.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 90)
        self.assertEqual(sum(r["status"] == "PASS" for r in rows), 90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
