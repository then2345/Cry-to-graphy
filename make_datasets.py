"""
make_datasets.py - Task 3: tạo 9 input theo Experimental Design mục 3 + dataset_manifest.csv

  TXT01/05/10 : lặp câu ASCII "Introduction to Cryptography benchmark. " rồi cắt đúng N byte
  IMG01/05/10 : BMP 24-bit không nén, rộng 1000 px, cao 333/1667/3333, gradient RGB xác định
  BIN01/05/10 : N byte ngẫu nhiên, sinh MỘT lần, lưu lại và dùng lại suốt thí nghiệm
  1 MB = 1,000,000 byte

Chạy: python make_datasets.py            (giữ nguyên file đã có -> không sinh lại binary)
      python make_datasets.py --force    (xóa và sinh lại toàn bộ; chỉ dùng TRƯỚC lần chạy chính thức)
"""
import argparse
import csv
import hashlib
import os
import random
import struct
import sys

DATA_DIR = "datasets"
SENTENCE = b"Introduction to Cryptography benchmark. "
SIZES = [("01", 1), ("05", 5), ("10", 10)]
IMG_WIDTH = 1000
IMG_HEIGHTS = {"01": 333, "05": 1667, "10": 3333}
BMP_HEADER = 54


def make_text(n: int) -> bytes:
    return (SENTENCE * (n // len(SENTENCE) + 1))[:n]


def make_bmp(width: int, height: int) -> bytes:
    row_bytes = width * 3                     # 1000*3 = 3000, chia hết cho 4 -> không padding
    assert row_bytes % 4 == 0
    pixel_bytes = row_bytes * height
    file_header = b"BM" + struct.pack("<IHHI", BMP_HEADER + pixel_bytes, 0, 0, BMP_HEADER)
    info_header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, pixel_bytes, 2835, 2835, 0, 0)
    base = bytearray()
    for x in range(width):
        base += bytes(((x * 255 // (width - 1)) & 0xFF, 0, 128))   # B theo x, R cố định
    rows = []
    for y in range(height):
        row = bytearray(base)
        row[1::3] = bytes([(y * 255 // max(height - 1, 1)) & 0xFF]) * width   # G theo y
        rows.append(bytes(row))
    return file_header + info_header + b"".join(rows)   # thứ tự byte pixel: B, G, R


def validate_bmp(data: bytes, width: int, height: int):
    """Kiểm tra header BMP hợp lệ; nếu có Pillow thì mở thử ảnh."""
    if data[:2] != b"BM":
        raise ValueError("missing BM signature")
    file_size, = struct.unpack_from("<I", data, 2)
    w, h = struct.unpack_from("<ii", data, 18)
    bpp, = struct.unpack_from("<H", data, 28)
    if file_size != len(data) or (w, h) != (width, height) or bpp != 24:
        raise ValueError(f"bad BMP header: size={file_size}, {w}x{h}, bpp={bpp}")
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(data)) as im:
            im.load()
            if im.size != (width, height):
                raise ValueError("Pillow reports wrong size")
        return "header OK; opened with Pillow"
    except ImportError:
        return "header OK (Pillow not installed)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed cho BIN deterministic (dùng cùng --force để sinh lại)")
    args = ap.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)

    specs = []
    for tag, mb in SIZES:
        specs.append((f"TXT{tag}", "text", mb * 1_000_000, f"TXT{tag}.txt"))
    for tag, mb in SIZES:
        specs.append((f"IMG{tag}", "image", mb * 1_000_000, f"IMG{tag}.bmp"))
    for tag, mb in SIZES:
        specs.append((f"BIN{tag}", "binary", mb * 1_000_000, f"BIN{tag}.bin"))

    rows = []
    for ds_id, dtype, target, fname in specs:
        path = os.path.join(DATA_DIR, fname)
        tag = ds_id[3:]
        generated_with_seed = False
        if os.path.exists(path) and not args.force:
            with open(path, "rb") as f:
                data = f.read()
            status = "kept existing file"
            if dtype == "binary" and args.seed is not None:
                status += " (use --force --seed to regenerate deterministically)"
        else:
            if dtype == "text":
                data = make_text(target)
            elif dtype == "image":
                data = make_bmp(IMG_WIDTH, IMG_HEIGHTS[tag])
            elif args.seed is None:
                data = os.urandom(target)
            else:
                data = random.Random(f"{args.seed}:{ds_id}").randbytes(target)
                generated_with_seed = True
            with open(path, "wb") as f:
                f.write(data)
            status = "generated"

        if dtype == "image":
            status += "; " + validate_bmp(data, IMG_WIDTH, IMG_HEIGHTS[tag])
        elif len(data) != target:
            sys.exit(f"{ds_id}: size {len(data)} != {target}")

        method = {
            "text": "repeat ASCII sentence, truncate to N bytes",
            "image": f"24-bit BMP {IMG_WIDTH}x{IMG_HEIGHTS.get(tag)} deterministic RGB gradient",
            "binary": (f"random.Random('{args.seed}:{ds_id}').randbytes(N) deterministic"
                       if generated_with_seed else "os.urandom(N) generated once and saved"),
        }[dtype]
        rows.append(dict(dataset_id=ds_id, data_type=dtype, target_size_bytes=target,
                         actual_size_bytes=len(data), filename=f"{DATA_DIR}/{fname}",
                         sha256=hashlib.sha256(data).hexdigest(), generation_method=method))
        print(f"{ds_id}: {len(data):>10,} B  {status}")

    with open("dataset_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("dataset_manifest.csv written (9 rows)")


if __name__ == "__main__":
    main()
