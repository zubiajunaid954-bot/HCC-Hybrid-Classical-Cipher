"""HCC - Hybrid Classical Cipher = Vigenere (substitution) then Rail Fence (transposition).

    encrypt:  plaintext -> Vigenere(keyword) -> Rail Fence(rails) -> ciphertext
    decrypt:  ciphertext -> Rail Fence^-1(rails) -> Vigenere^-1(keyword) -> plaintext

Decryption undoes the stages in REVERSE order, like taking off shoes and
socks: the last operation applied must be the first one removed.
Secret key = (keyword, rails).  Time O(n), space O(n).
"""

import rail_fence
import vigenere
from utils import require_message, validate_keyword, validate_rails


def encrypt_with_trace(plaintext, keyword, rails):
    """Return (normalized_plaintext, stage1_output, ciphertext) for teaching/demo output."""
    keyword = validate_keyword(keyword)
    rails = validate_rails(rails)
    normalized = require_message(plaintext)
    stage1 = vigenere.encrypt(normalized, keyword)
    return normalized, stage1, rail_fence.encrypt(stage1, rails)


def encrypt(plaintext, keyword, rails):
    """Encrypt `plaintext` with HCC and return the ciphertext."""
    return encrypt_with_trace(plaintext, keyword, rails)[2]


def decrypt_with_trace(ciphertext, keyword, rails):
    """Return (normalized_ciphertext, stage1_output_recovered, plaintext)."""
    keyword = validate_keyword(keyword)
    rails = validate_rails(rails)
    normalized = require_message(ciphertext, "ciphertext")
    stage1 = rail_fence.decrypt(normalized, rails)
    return normalized, stage1, vigenere.decrypt(stage1, keyword)


def decrypt(ciphertext, keyword, rails):
    """Decrypt an HCC `ciphertext` and return the (normalized) plaintext."""
    return decrypt_with_trace(ciphertext, keyword, rails)[2]
