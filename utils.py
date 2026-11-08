"""Shared helpers: alphabet handling, input normalization and key validation.

All ciphers in this project work on the 26 uppercase English letters A-Z,
mapped to the integers 0-25 (A=0, B=1, ..., Z=25).
"""

import string

ALPHABET = string.ascii_uppercase
ALPHABET_SIZE = 26
MIN_KEYWORD_LENGTH = 10
MIN_RAILS = 2


class ValidationError(ValueError):
    """Raised when user input (message, keyword, rails, ...) is invalid."""


def char_to_num(char):
    """Map 'A'..'Z' to 0..25."""
    return ord(char) - ord("A")


def num_to_char(number):
    """Map any integer to a letter using arithmetic modulo 26."""
    return ALPHABET[number % ALPHABET_SIZE]


def normalize_text(text):
    """Convert free text to the cipher alphabet.

    Rules (applied identically everywhere in the project):
      * letters are converted to uppercase;
      * every character that is not an English letter A-Z (spaces, digits,
        punctuation, accented letters, newlines) is REMOVED.

    Formatting is deliberately not preserved: keeping spaces or punctuation
    would leak word lengths and sentence structure to an attacker.
    """
    if not isinstance(text, str):
        raise ValidationError("Text must be a string.")
    return "".join(ch for ch in text.upper() if ch in ALPHABET)


def require_message(text, what="message"):
    """Normalize text and make sure something is left after normalization."""
    cleaned = normalize_text(text)
    if not cleaned:
        raise ValidationError(
            f"The {what} is empty after normalization "
            "(it must contain at least one letter A-Z)."
        )
    return cleaned


def smallest_period(word):
    """Length of the shortest word that, repeated, builds `word` exactly.

    'ABCABCABCABC' -> 3, 'SECURITYKEYS' -> 12 (no shorter repeating unit).
    """
    length = len(word)
    for period in range(1, length + 1):
        if length % period == 0 and word == word[:period] * (length // period):
            return period
    return length


def validate_keyword(keyword, min_length=MIN_KEYWORD_LENGTH):
    """Validate and normalize a Vigenere keyword.

    Requirements: letters A-Z only (case-insensitive), at least `min_length`
    characters, and not a repetition of a shorter word (otherwise the
    *effective* key length would drop below the required minimum).
    """
    if not isinstance(keyword, str):
        raise ValidationError("Keyword must be a string.")
    key = keyword.strip().upper()
    if not key or any(ch not in ALPHABET for ch in key):
        raise ValidationError("Keyword must contain only letters A-Z (no spaces or digits).")
    if len(key) < min_length:
        raise ValidationError(
            f"Keyword must be at least {min_length} characters long (got {len(key)})."
        )
    period = smallest_period(key)
    if period < min_length:
        raise ValidationError(
            f"Weak keyword: it is just '{key[:period]}' repeated, so its effective "
            f"length is {period} (< {min_length})."
        )
    return key


def validate_rails(rails):
    """Validate the Rail Fence key (an integer >= 2)."""
    if isinstance(rails, bool):
        raise ValidationError("Number of rails must be an integer.")
    try:
        value = int(rails)
    except (TypeError, ValueError):
        raise ValidationError("Number of rails must be an integer.") from None
    if isinstance(rails, float) and rails != value:
        raise ValidationError("Number of rails must be an integer.")
    if value < MIN_RAILS:
        raise ValidationError(f"Number of rails must be at least {MIN_RAILS}.")
    return value


def group_text(text, size=5):
    """Insert a space every `size` letters (display only, e.g. 'ABCDE FGHIJ')."""
    return " ".join(text[i:i + size] for i in range(0, len(text), size))
