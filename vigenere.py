"""Stage 1 - Vigenere cipher (polyalphabetic substitution).

Encryption:  C[i] = (P[i] + K[i mod m]) mod 26
Decryption:  P[i] = (C[i] - K[i mod m]) mod 26
where m is the keyword length.  Time O(n), space O(n).
"""

from utils import char_to_num, num_to_char, require_message, validate_keyword


def _shift_text(text, keyword, direction):
    key_numbers = [char_to_num(ch) for ch in keyword]
    key_length = len(key_numbers)
    return "".join(
        num_to_char(char_to_num(ch) + direction * key_numbers[i % key_length])
        for i, ch in enumerate(text)
    )


def encrypt(plaintext, keyword):
    """Vigenere-encrypt `plaintext` (normalized to A-Z) with `keyword`."""
    return _shift_text(require_message(plaintext), validate_keyword(keyword), +1)


def decrypt(ciphertext, keyword):
    """Vigenere-decrypt `ciphertext` with `keyword`."""
    return _shift_text(require_message(ciphertext, "ciphertext"), validate_keyword(keyword), -1)
