"""Attacks on HCC.

1. known_plaintext_attack  - the main attack (assignment requirement 6).
2. ciphertext_only_attack  - bonus: shows that HCC also falls to frequency
   statistics once enough ciphertext is available.

THREAT MODEL (what the attacker is given, and what must be recovered)
---------------------------------------------------------------------
Assumed KNOWN to the attacker (Kerckhoffs' principle):
  * the architecture: Vigenere first, Rail Fence second;
  * the full ciphertext C (n letters);
  * a known plaintext segment P_known (k letters) and its position
    (`known_offset`) inside the original message;
  * the keyword length m (or a small range of candidates) and a range of
    possible rail counts [r_min, r_max].

MUST BE RECOVERED (never passed to the attack function):
  * the Rail Fence key r;
  * the Vigenere keyword K (m letters);
  * consequently the entire plaintext.

MATHEMATICS
-----------
Encryption:  V[i] = (P[i] + K[i mod m]) mod 26      (Vigenere)
             C    = RailFence_r(V)                  (a fixed permutation of V)
For a guessed rail count r the attacker applies the inverse permutation:
             V'[i] = C[pos_r(i)]       (V' == V exactly when r is correct)
and for each known plaintext position i = offset + t  (t = 0..k-1):
             K'[i mod m] = (V'[i] - P[i]) mod 26
If r is right, every position i with the same residue (i mod m) yields the
SAME key letter -> the derived key is a consistent repeating keyword.
If r is wrong, V' is a scrambled version of V and two positions that share a
residue agree only by chance, with probability about 1/26 each.  With
redundancy rho = k - min(k, m) extra equations, a wrong rail count survives
the consistency test with probability about 26^(-rho).
Hence: k <= m gives no redundancy (every r looks consistent), k > m is needed
for a reliable result, and k >= m is needed to recover the whole keyword.
"""

import time
from dataclasses import dataclass, field

import hybrid_cipher
import rail_fence
from frequency_analysis import chi_squared, chi_squared_from_counts
from utils import (ALPHABET_SIZE, ValidationError, char_to_num, num_to_char,
                   require_message, validate_rails)

UNKNOWN = "?"


@dataclass
class Candidate:
    """A (rails, key length) hypothesis that passed the consistency test."""
    rails: int
    key_length: int
    keyword: str            # recovered key letters, '?' where the segment did not reach
    covered: int            # how many of the m key positions were determined
    redundancy: int         # known letters beyond those needed to determine the key
    fitness: float = float("inf")   # chi-squared of the decrypted text (lower = better)

    @property
    def complete(self):
        return self.covered == self.key_length


@dataclass
class TraceRow:
    """One line of the search log: what happened for a given hypothesis."""
    rails: int
    key_length: int
    derived_key: str
    conflicts: int
    consistent: bool


@dataclass
class AttackResult:
    status: str                      # "recovered", "partial" or "failed"
    message: str
    selected: Candidate = None
    consistent: list = field(default_factory=list)
    plaintext: str = None
    verified: bool = False           # recovered keys re-encrypt the plaintext to the ciphertext
    candidates_tested: int = 0
    char_operations: int = 0
    elapsed_seconds: float = 0.0
    trace: list = field(default_factory=list)

    @property
    def ambiguous(self):
        return len(self.consistent) > 1


def _as_list(key_lengths):
    if isinstance(key_lengths, int):
        key_lengths = [key_lengths]
    key_lengths = sorted(set(key_lengths))
    if not key_lengths or key_lengths[0] < 1:
        raise ValidationError("Key length(s) must be positive integers.")
    return key_lengths


def _rails_to_test(length, rail_range):
    """Rail counts to try. Any r >= length gives the identity permutation, so
    trying one such value is enough."""
    low, high = rail_range
    low = validate_rails(low)
    if high < low:
        raise ValidationError("Maximum rails must be at least the minimum rails.")
    return [r for r in range(low, high + 1) if r <= max(length, low)]


def undo_rail_fence_raw(ciphertext, rails):
    """Inverse zig-zag permutation (same as rail_fence.decrypt, without re-validation)."""
    restored = [""] * len(ciphertext)
    for letter, position in zip(ciphertext, rail_fence.rail_order(len(ciphertext), rails)):
        restored[position] = letter
    return "".join(restored)


def _subtract_key(text, key_numbers):
    m = len(key_numbers)
    return "".join(num_to_char(char_to_num(ch) - key_numbers[i % m]) for i, ch in enumerate(text))


def derivation_table(ciphertext, known_plaintext, rails, key_length, known_offset=0, rows=None):
    """Intermediate calculations of the attack for ONE hypothesis (used in the demo/report).

    Returns tuples (index, plain_letter, stage1_letter, key_position, key_letter)
    where key_letter = (stage1_letter - plain_letter) mod 26.
    """
    ciphertext = require_message(ciphertext, "ciphertext")
    known_plaintext = require_message(known_plaintext, "known plaintext")
    stage1 = undo_rail_fence_raw(ciphertext, rails)
    table = []
    for t, plain in enumerate(known_plaintext):
        index = known_offset + t
        derived = num_to_char(char_to_num(stage1[index]) - char_to_num(plain))
        table.append((index, plain, stage1[index], index % key_length, derived))
        if rows is not None and len(table) >= rows:
            break
    return table


def explain_guess(ciphertext, known_plaintext, rails, key_length, known_offset=0):
    """Every intermediate value of the attack for ONE (rails, key length) guess.

    Used by the step-by-step view in the interface. The arithmetic is the same as in
    known_plaintext_attack: undo the fence, then K = (V' - P) mod 26 for each known letter,
    and a letter that lands on an already-filled keyword position must agree with it.
    Each known letter is reported with status "new" (first letter for that keyword
    position), "agrees" or "conflict".
    """
    ciphertext = require_message(ciphertext, "ciphertext")
    known_plaintext = require_message(known_plaintext, "known plaintext")
    stage1 = undo_rail_fence_raw(ciphertext, rails)
    slots = [None] * key_length
    letters, conflicts = [], 0
    for t, plain in enumerate(known_plaintext):
        index = known_offset + t
        slot = index % key_length
        key = num_to_char(char_to_num(stage1[index]) - char_to_num(plain))
        if slots[slot] is None:
            slots[slot], status = key, "new"
        elif slots[slot] == key:
            status = "agrees"
        else:
            status, conflicts = "conflict", conflicts + 1
        letters.append({"index": index, "plain": plain, "stage1": stage1[index],
                        "slot": slot, "key": key, "status": status})
    return {
        "rails": rails,
        "key_length": key_length,
        "stage1": stage1,
        "pattern": rail_fence.rail_pattern(len(ciphertext), rails),
        "letters": letters,
        "keyword": "".join(UNKNOWN if s is None else s for s in slots),
        "conflicts": conflicts,
        "consistent": conflicts == 0,
    }


def known_plaintext_attack(ciphertext, known_plaintext, key_lengths, rail_range=(2, 20),
                           known_offset=0, use_language_model=True):
    """Recover the HCC keys from a known plaintext segment.

    Parameters
    ----------
    ciphertext          full HCC ciphertext (letters A-Z).
    known_plaintext     the k known plaintext letters.
    key_lengths         assumed Vigenere keyword length m (int) or iterable of candidates.
    rail_range          (min_rails, max_rails) search range for the Rail Fence key.
    known_offset        index in the original message where known_plaintext starts.
    use_language_model  if several hypotheses survive the consistency test, rank them by
                        how English-like the decrypted text is (otherwise the result is
                        reported as ambiguous and the first one is chosen).
    """
    started = time.perf_counter()
    ciphertext = require_message(ciphertext, "ciphertext")
    known_plaintext = require_message(known_plaintext, "known plaintext")
    lengths = _as_list(key_lengths)
    n, k = len(ciphertext), len(known_plaintext)
    if known_offset < 0 or known_offset + k > n:
        raise ValidationError(
            f"The known segment (offset {known_offset}, length {k}) does not fit inside "
            f"a ciphertext of length {n}."
        )
    known_numbers = [char_to_num(ch) for ch in known_plaintext]

    result = AttackResult(status="failed", message="")
    rails_list = _rails_to_test(n, rail_range)

    for rails in rails_list:                                  # step 1: guess the rail count
        stage1 = undo_rail_fence_raw(ciphertext, rails)       # step 2: reverse Rail Fence
        result.char_operations += n
        stage1_numbers = [char_to_num(stage1[known_offset + t]) for t in range(k)]
        for m in lengths:
            result.candidates_tested += 1
            result.char_operations += k
            key_slots = [None] * m                            # step 3: K'[i mod m] = V'[i] - P[i]
            conflicts = 0
            for t in range(k):
                slot = (known_offset + t) % m
                derived = (stage1_numbers[t] - known_numbers[t]) % ALPHABET_SIZE
                if key_slots[slot] is None:
                    key_slots[slot] = derived
                elif key_slots[slot] != derived:
                    conflicts += 1                            # step 4: consistency check
            keyword = "".join(UNKNOWN if v is None else num_to_char(v) for v in key_slots)
            consistent = conflicts == 0
            result.trace.append(TraceRow(rails, m, keyword, conflicts, consistent))
            if consistent:
                covered = sum(v is not None for v in key_slots)
                result.consistent.append(Candidate(rails, m, keyword, covered, k - covered))

    if not result.consistent:
        result.message = ("No (rails, key length) hypothesis is consistent with the known "
                          "plaintext. Check the assumptions (key length, rail range, offset, "
                          "or whether the known text really matches this ciphertext).")
        result.elapsed_seconds = time.perf_counter() - started
        return result

    # step 5: rank the surviving hypotheses
    for candidate in result.consistent:
        if candidate.complete:
            plain = _decrypt_with(ciphertext, candidate)
            result.char_operations += n
            if use_language_model:
                candidate.fitness = chi_squared(plain)
    result.consistent.sort(key=lambda c: (not c.complete,
                                          c.fitness if use_language_model else 0.0,
                                          -c.redundancy, c.rails, c.key_length))
    best = result.consistent[0]
    result.selected = best

    if not best.complete:
        result.status = "partial"
        result.message = (f"INSUFFICIENT KNOWN PLAINTEXT: the segment covers only {best.covered} of "
                          f"{best.key_length} key positions, so the keyword cannot be recovered "
                          f"completely, and {len(result.consistent)} rail count(s) remain possible "
                          f"(first listed: rails={best.rails}, partial key {best.keyword}). "
                          f"Supply more than {best.key_length} known letters.")
    else:
        # step 6: decrypt everything with the recovered keys
        result.plaintext = _decrypt_with(ciphertext, best)
        result.char_operations += n
        result.verified = _reencrypts_to(result.plaintext, best, ciphertext)
        result.status = "recovered"
        note = ""
        if result.ambiguous:
            note = (f" NOTE: {len(result.consistent)} hypotheses survived the consistency "
                    "test; the most English-like one was chosen." if use_language_model else
                    f" NOTE: {len(result.consistent)} hypotheses survived the consistency "
                    "test; the first was chosen (use a longer known segment).")
        result.message = (f"Recovered rails={best.rails}, keyword={best.keyword}." + note)
    result.elapsed_seconds = time.perf_counter() - started
    return result


def _decrypt_with(ciphertext, candidate):
    key_numbers = [char_to_num(ch) for ch in candidate.keyword]
    return _subtract_key(undo_rail_fence_raw(ciphertext, candidate.rails), key_numbers)


def _reencrypt_raw(plaintext, candidate):
    key_numbers = [char_to_num(ch) for ch in candidate.keyword]
    m = len(key_numbers)
    stage1 = "".join(num_to_char(char_to_num(ch) + key_numbers[i % m])
                     for i, ch in enumerate(plaintext))
    return "".join(stage1[p] for p in rail_fence.rail_order(len(stage1), candidate.rails))


def _reencrypts_to(plaintext, candidate, ciphertext):
    """End-to-end check: the recovered keys must map the recovered plaintext back to the
    supplied ciphertext (uses the real HCC code when the keyword is a legal HCC key)."""
    try:
        return hybrid_cipher.encrypt(plaintext, candidate.keyword, candidate.rails) == ciphertext
    except ValidationError:
        return _reencrypt_raw(plaintext, candidate) == ciphertext


# ---------------------------------------------------------------------------
# Bonus: ciphertext-only attack (frequency statistics + search over rail counts)
# ---------------------------------------------------------------------------

@dataclass
class CiphertextOnlyResult:
    rails: int
    keyword: str
    plaintext: str
    ranking: list                    # [(rails, score)] best first
    candidates_tested: int
    char_operations: int
    elapsed_seconds: float


def ciphertext_only_attack(ciphertext, key_length, rail_range=(2, 20)):
    """Break HCC with NO known plaintext, using English letter statistics.

    For every rail count r: undo the Rail Fence, split the result into m
    columns (positions with the same i mod m - each column is a Shift cipher),
    pick for each column the shift whose letter distribution is closest to
    English (chi-squared) and add the column scores.  The rail count with the
    lowest total score wins.  Needs a long ciphertext (several dozen letters
    per key position); with short texts it fails - which the experiments show.
    """
    started = time.perf_counter()
    ciphertext = require_message(ciphertext, "ciphertext")
    n, m = len(ciphertext), key_length
    if m < 1:
        raise ValidationError("Key length must be a positive integer.")
    ranking, best, operations = [], None, 0
    for rails in _rails_to_test(n, rail_range):
        stage1 = undo_rail_fence_raw(ciphertext, rails)
        operations += n * 2
        total, shifts = 0.0, []
        for column in range(m):
            counts = [0] * ALPHABET_SIZE
            for ch in stage1[column::m]:
                counts[char_to_num(ch)] += 1
            scores = [chi_squared_from_counts(counts, s) for s in range(ALPHABET_SIZE)]
            operations += ALPHABET_SIZE * ALPHABET_SIZE
            shift = min(range(ALPHABET_SIZE), key=scores.__getitem__)
            shifts.append(shift)
            total += scores[shift]
        ranking.append((rails, total))
        if best is None or total < best[1]:
            best = (rails, total, shifts)
    ranking.sort(key=lambda pair: pair[1])
    rails, _, shifts = best
    plaintext = _subtract_key(undo_rail_fence_raw(ciphertext, rails), shifts)
    keyword = "".join(num_to_char(s) for s in shifts)
    return CiphertextOnlyResult(rails, keyword, plaintext, ranking, len(ranking), operations,
                                time.perf_counter() - started)
