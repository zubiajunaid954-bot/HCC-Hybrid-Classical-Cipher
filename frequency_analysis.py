"""Letter-frequency tools used for security analysis.

* letter counts / relative frequencies
* chi-squared distance from standard English
* index of coincidence (IC)
* a frequency attack that breaks the single-stage Shift cipher

English reference frequencies are the commonly cited values from
R. Lewand, "Cryptological Mathematics" (MAA, 2000).
"""

from utils import ALPHABET, ALPHABET_SIZE, char_to_num, normalize_text

# Standard English letter probabilities, in percent, for A..Z.
ENGLISH_PERCENT = [
    8.167, 1.492, 2.782, 4.253, 12.702, 2.228, 2.015, 6.094, 6.966, 0.153,
    0.772, 4.025, 2.406, 6.749, 7.507, 1.929, 0.095, 5.987, 6.327, 9.056,
    2.758, 0.978, 2.360, 0.150, 1.974, 0.074,
]
ENGLISH_FREQ = [p / sum(ENGLISH_PERCENT) for p in ENGLISH_PERCENT]  # sums to exactly 1

IC_ENGLISH = sum(f * f for f in ENGLISH_FREQ)   # about 0.0655
IC_RANDOM = 1 / ALPHABET_SIZE                   # 0.0385 for uniformly random letters


def letter_counts(text):
    """Return a list of 26 counts (index 0 = 'A')."""
    counts = [0] * ALPHABET_SIZE
    for ch in normalize_text(text):
        counts[char_to_num(ch)] += 1
    return counts


def letter_frequencies(text):
    """Return a list of 26 relative frequencies (all zero for empty text)."""
    counts = letter_counts(text)
    total = sum(counts)
    return [c / total for c in counts] if total else [0.0] * ALPHABET_SIZE


def chi_squared_from_counts(counts, shift=0):
    """Chi-squared distance between observed counts and English.

    `shift` tests the hypothesis "this text is English shifted by `shift`":
    letter L of the hypothetical plaintext is observed as letter L+shift.
    Lower is more English-like.
    """
    total = sum(counts)
    if total == 0:
        return float("inf")
    score = 0.0
    for letter in range(ALPHABET_SIZE):
        expected = ENGLISH_FREQ[letter] * total
        observed = counts[(letter + shift) % ALPHABET_SIZE]
        score += (observed - expected) ** 2 / expected
    return score


def chi_squared(text):
    """Chi-squared distance of `text` from standard English letter frequencies."""
    return chi_squared_from_counts(letter_counts(text))


def index_of_coincidence(text):
    """IC = sum n_i (n_i - 1) / (N (N - 1)): chance two random letters of the text match."""
    counts = letter_counts(text)
    total = sum(counts)
    if total < 2:
        return 0.0
    return sum(c * (c - 1) for c in counts) / (total * (total - 1))


def break_shift_by_frequency(ciphertext):
    """Frequency attack on the Shift cipher.

    Try all 26 shifts, rank them by chi-squared against English and return
    (best_shift, ranking) where ranking is [(shift, score), ...] best first.
    """
    counts = letter_counts(ciphertext)
    ranking = sorted(
        ((shift, chi_squared_from_counts(counts, shift)) for shift in range(ALPHABET_SIZE)),
        key=lambda pair: pair[1],
    )
    return ranking[0][0], ranking


def frequency_report(text, bar_width=40):
    """Human-readable table: counts, observed %, English %, bar, plus IC and chi-squared."""
    counts = letter_counts(text)
    total = sum(counts)
    if total == 0:
        return "No letters to analyse."
    top = max(counts) / total
    lines = [f"{'Ltr':<4}{'Count':>6}{'Obs %':>8}{'Eng %':>8}  Distribution"]
    for i, letter in enumerate(ALPHABET):
        observed = counts[i] / total
        bar = "#" * round(bar_width * observed / top) if top else ""
        lines.append(f"{letter:<4}{counts[i]:>6}{observed * 100:>8.2f}{ENGLISH_PERCENT[i]:>8.2f}  {bar}")
    lines.append("")
    lines.append(f"Total letters      : {total}")
    lines.append(f"Index of coincidence: {index_of_coincidence(text):.4f}"
                 f"   (English ~ {IC_ENGLISH:.4f}, random ~ {IC_RANDOM:.4f})")
    lines.append(f"Chi-squared vs English: {chi_squared(text):.1f}   (lower = more English-like)")
    return "\n".join(lines)
