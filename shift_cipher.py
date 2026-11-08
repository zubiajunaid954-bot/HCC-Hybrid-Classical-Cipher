"""Single-stage baseline: the Shift (Caesar) cipher.

C[i] = (P[i] + k) mod 26,   P[i] = (C[i] - k) mod 26.   Time O(n), space O(n).
Only 26 keys exist, so it is trivially broken by brute force or frequency analysis.
"""

from utils import ALPHABET_SIZE, ValidationError, char_to_num, num_to_char, require_message


def validate_shift(shift):
    """Shift must be an integer; it is reduced modulo 26."""
    if isinstance(shift, bool) or not isinstance(shift, int):
        raise ValidationError("Shift key must be an integer.")
    return shift % ALPHABET_SIZE


def encrypt(plaintext, shift):
    shift = validate_shift(shift)
    return "".join(num_to_char(char_to_num(ch) + shift) for ch in require_message(plaintext))


def decrypt(ciphertext, shift):
    shift = validate_shift(shift)
    return "".join(
        num_to_char(char_to_num(ch) - shift) for ch in require_message(ciphertext, "ciphertext")
    )
