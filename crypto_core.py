"""
crypto_core.py - Task 3 Implementation: AES-256-GCM và ChaCha20-Poly1305 (AEAD)
Dùng thư viện `cryptography`, không tự cài đặt primitive (Experimental Design mục 1-2).

Cấu hình chung cho cả hai thuật toán:
    key 256 bit (32 B), nonce 96 bit (12 B), tag 128 bit (16 B), AAD = None
    package lưu trữ = nonce || ciphertext || tag   (overhead 28 B)
"""
import os

from cryptography.exceptions import InvalidTag  # noqa: F401  (re-export cho các module khác)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

KEY_SIZE = 32
NONCE_SIZE = 12
TAG_SIZE = 16
AAD = None

ALGORITHMS = {
    "AES-256-GCM": AESGCM,
    "ChaCha20-Poly1305": ChaCha20Poly1305,
}
ALGORITHM_NAMES = list(ALGORITHMS)


def new_key() -> bytes:
    """Sinh key ngẫu nhiên 256 bit."""
    return os.urandom(KEY_SIZE)


def make_cipher(algorithm: str, key: bytes):
    """Tạo cipher object (làm NGOÀI vùng đo thời gian)."""
    if len(key) != KEY_SIZE:
        raise ValueError("key must be 32 bytes")
    return ALGORITHMS[algorithm](key)


class NonceCounter:
    """Nonce = bộ đếm tăng dần, mã hóa 12 byte big-endian.
    Mỗi scenario dùng key mới + counter mới, nên không bao giờ lặp (key, nonce)."""

    def __init__(self):
        self._n = 0

    def next(self) -> bytes:
        self._n += 1
        return self._n.to_bytes(NONCE_SIZE, "big")

    @property
    def used(self) -> int:
        return self._n


def encrypt(cipher, nonce: bytes, plaintext: bytes) -> bytes:
    """Trả về ciphertext || tag (16 B cuối là tag)."""
    return cipher.encrypt(nonce, plaintext, AAD)


def decrypt(cipher, nonce: bytes, api_output: bytes) -> bytes:
    """Ném InvalidTag nếu key/nonce/ciphertext/tag sai."""
    return cipher.decrypt(nonce, api_output, AAD)


def split_output(api_output: bytes):
    """Tách kết quả encrypt() thành (ciphertext, tag)."""
    return api_output[:-TAG_SIZE], api_output[-TAG_SIZE:]


def to_package(nonce: bytes, api_output: bytes) -> bytes:
    """Định dạng lưu trữ: nonce || ciphertext || tag."""
    return nonce + api_output


def from_package(package: bytes):
    """Ngược lại của to_package -> (nonce, ciphertext||tag)."""
    return package[:NONCE_SIZE], package[NONCE_SIZE:]


if __name__ == "__main__":
    # Demo nhanh
    msg = b"Introduction to Cryptography benchmark. "
    for name in ALGORITHM_NAMES:
        c = make_cipher(name, new_key())
        n = NonceCounter().next()
        out = encrypt(c, n, msg)
        pkg = to_package(n, out)
        assert decrypt(c, *from_package(pkg)) == msg
        print(f"{name:18} plaintext={len(msg)} B  package={len(pkg)} B  overhead={len(pkg) - len(msg)} B")
