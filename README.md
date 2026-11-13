# AES-256-GCM vs ChaCha20-Poly1305

## Yêu cầu

- **Python 3.14.5** — phiên bản đã dùng để tạo bộ S01. Nên dùng đúng phiên bản này khi tái lập số đo.
- Cài đặt:

```bash
python -m pip install -r requirements.txt
```

`cryptography==48.0.0` là thư viện thực hiện AES-256-GCM và ChaCha20-Poly1305; được pin đúng phiên bản S01. Các package còn lại (`pandas`, `matplotlib`, `py-cpuinfo`, `psutil`, `pillow`) chỉ phục vụ phân tích, vẽ hình và ghi thông tin môi trường. Nếu thiếu `py-cpuinfo`/`psutil`/`pillow`, chương trình vẫn chạy nhưng `environment.json` có thể ghi `unknown` và bước kiểm tra BMP bằng Pillow bị bỏ qua.

## Chạy toàn bộ

Cắm sạc, chọn chế độ hiệu năng cao, tắt ứng dụng khác, rồi chạy từ thư mục gốc repo:

```bash
python run_all.py --session S01 --power "plugged-in, best performance"
```

- Cả hai thuật toán chạy trên **cùng một máy, cùng một lần chạy**.
- `source_revision` được tự động lấy từ `git rev-parse HEAD` nếu repo là git; nếu chưa phải git, chương trình ghi SHA-256 của source.
- Có thể chỉ định commit thủ công: `--revision <commit>`.
- Với lần chạy mới muốn BIN deterministic, thêm `--seed 20261112`; `run_all.py` sẽ sinh lại toàn bộ dataset bằng `make_datasets.py --force --seed ...` trước khi đo.

## Vị trí kết quả

Tất cả output của lần chạy được ghi vào **thư mục hiện tại (repo root)**. Bộ S01 đã nộp gồm:

| File | Nội dung |
|---|---|
| `functional_tests.csv` | 90 dòng: 5 test × 2 thuật toán × 9 dataset, 90/90 PASS |
| `raw_measurements.csv` | 540 dòng đo thô: 18 scenario × 30 lần, có `enc_ns`/`dec_ns` từng lần |
| `summary.csv` | 18 dòng tổng hợp: mean, SD, median, CI 95%, throughput, overhead |
| `config.json` | Cấu hình thuật toán, nonce/tag, warm-up 5, measured 30, thứ tự chạy |
| `dataset_manifest.csv` | 9 dataset + kích thước thực + SHA-256 |
| `environment.json` | CPU, RAM, OS, Python, cryptography/OpenSSL, timer, power, source revision |
| `fig_latency.png` | Latency vs kích thước, error bar 95% CI |
| `fig_throughput.png` | Throughput encrypt/decrypt |
| `fig_flow.png` | Sơ đồ luồng chương trình |

Thư mục `datasets/` được tạo bởi `make_datasets.py` và **không commit mặc định** (xem phần tái lập bên dưới).

## Checklist output S01

- [x] `functional_tests.csv`: 90/90 PASS
- [x] `raw_measurements.csv`: 540 dòng
- [x] `summary.csv`: 18 dòng, `n = 30` mỗi scenario
- [x] `config.json` và `dataset_manifest.csv`
- [x] `environment.json`: không còn `TO RECORD`; có `source_revision`
- [x] `fig_latency.png`, `fig_throughput.png`, `fig_flow.png`
- [x] Tất cả output cùng `session_id = S01` và `protocol_version = v1`

## Các file source

| File | Task | Vai trò |
|---|---|---|
| `crypto_core.py` | 3 | Mã hóa/giải mã AEAD, key/nonce, định dạng `nonce‖ciphertext‖tag` |
| `make_datasets.py` | 3 | Tạo 9 input (TXT/IMG/BIN × 1/5/10 MB) + `dataset_manifest.csv` (SHA-256) |
| `benchmark.py` | 3 | 5 warm-up + 30 lần đo / scenario, xen kẽ thứ tự → `raw_measurements.csv`, `config.json` |
| `collect_env.py` | 4 | Thông tin máy/phần mềm + source revision → `environment.json` |
| `functional_tests.py` | 4 | 5 test × 18 scenario = 90 dòng → `functional_tests.csv` |
| `analyze.py` | 4 | Mean, SD, median, 95% CI, throughput → `summary.csv`, `fig_latency.png`, `fig_throughput.png` |
| `flow_diagram.py` | 4 | Sơ đồ luồng chương trình → `fig_flow.png` |
| `run_all.py` | — | Chạy tất cả theo đúng thứ tự |
| `requirements.txt` | — | Phiên bản Python/thư viện dùng cho S01 |

## Tái lập dataset

- **TXT01/05/10** và **IMG01/05/10** là deterministic. Chạy `python make_datasets.py --force` sẽ tạo lại đúng SHA-256 trong `dataset_manifest.csv`.
- **BIN01/05/10** của S01 được sinh bằng `os.urandom(N)` nên **không thể tái tạo chính xác** nếu không có file gốc. Repo không commit `datasets/`; nếu cần tái lập đúng S01, lấy `BIN*.bin` từ máy đã chạy S01 và kiểm tra SHA-256 với `dataset_manifest.csv`.
- Với lần chạy mới, có thể sinh BIN deterministic:

```bash
python make_datasets.py --force --seed 20261112
```

Khi dùng `--seed`, cột `generation_method` trong manifest ghi rõ seed; chạy lại cùng seed sẽ cho cùng dữ liệu BIN.

- Kích thước ảnh BMP thực tế xấp xỉ 1/5/10 MB (do header 54 B và chiều cao nguyên): IMG01 = 999.054 B, IMG05 = 5.001.054 B, IMG10 = 9.999.054 B. Phân tích dùng `actual_size_bytes`, không dùng kích thước danh nghĩa.

## Source revision

`collect_env.py` tự động ghi commit hash nếu chạy trong git repo; nếu không, ghi `sha256:<hash>` của source. Sau khi commit/push lần đầu, chỉ cần cập nhật lại trường này mà không đổi các thông số môi trường đã đo:

```bash
python collect_env.py --update-revision-only
```

Không ghi key, nonce hoặc dữ liệu bí mật vào repo.

## Lưu ý

- Dữ liệu binary sinh **một lần** rồi dùng lại. Chỉ dùng `make_datasets.py --force` trước lần chạy chính thức.
- Kết quả là hiệu năng API trong bộ nhớ trên **một máy cụ thể**, không phải kết luận phổ quát.
- `overhead_bytes = 28` B là overhead của package lưu trữ (`nonce 12 B + tag 16 B`), không phải chỉ riêng tag.
