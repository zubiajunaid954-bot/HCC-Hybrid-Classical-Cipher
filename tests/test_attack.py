"""Tests for the attacks, frequency analysis and experiment code."""

import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import attack
import frequency_analysis as fa
import hybrid_cipher
import performance
import sample_data
import shift_cipher
from utils import ValidationError

KEY = "SECURITYKEYS"


def make_case(seed, n, rails=None):
    rng = sample_data.make_rng(seed)
    keyword = sample_data.generate_random_keyword(12, rng)
    rails = rails or rng.randint(2, 20)
    plain = sample_data.generate_english_text(n, rng)
    return plain, keyword, rails, hybrid_cipher.encrypt(plain, keyword, rails)


class TestKnownPlaintextAttack(unittest.TestCase):
    def test_attack_never_receives_secret_keys(self):
        parameters = set(inspect.signature(attack.known_plaintext_attack).parameters)
        self.assertEqual(parameters, {"ciphertext", "known_plaintext", "key_lengths", "rail_range",
                                      "known_offset", "use_language_model"})

    def test_successful_recovery_many_cases(self):
        for seed in range(60):
            plain, keyword, rails, cipher = make_case(seed, 200 + 10 * seed)
            with self.subTest(seed=seed):
                result = attack.known_plaintext_attack(cipher, plain[:24], 12, (2, 20))
                self.assertEqual(result.status, "recovered")
                self.assertEqual(result.selected.rails, rails)
                self.assertEqual(result.selected.keyword, keyword)
                self.assertEqual(result.plaintext, plain)
                self.assertTrue(result.verified)

    def test_recovered_keys_reproduce_supplied_ciphertext(self):
        plain, keyword, rails, cipher = make_case(5, 400)
        result = attack.known_plaintext_attack(cipher, plain[:30], 12, (2, 20))
        self.assertEqual(hybrid_cipher.encrypt(result.plaintext, result.selected.keyword,
                                               result.selected.rails), cipher)

    def test_unique_survivor_with_enough_redundancy(self):
        plain, _, _, cipher = make_case(9, 500)
        result = attack.known_plaintext_attack(cipher, plain[:30], 12, (2, 20))
        self.assertEqual(len(result.consistent), 1)
        self.assertFalse(result.ambiguous)

    def test_exact_key_length_segment_is_ambiguous_without_language_model(self):
        plain, _, rails, cipher = make_case(3, 300)
        result = attack.known_plaintext_attack(cipher, plain[:12], 12, (2, 20), use_language_model=False)
        self.assertGreater(len(result.consistent), 1)       # no redundancy: every rail count fits
        self.assertTrue(result.ambiguous)

    def test_exact_key_length_segment_resolved_by_language_model(self):
        plain, keyword, rails, cipher = make_case(3, 600)
        result = attack.known_plaintext_attack(cipher, plain[:12], 12, (2, 20))
        self.assertEqual((result.selected.rails, result.selected.keyword), (rails, keyword))

    def test_insufficient_known_plaintext_gives_partial_key(self):
        plain, keyword, rails, cipher = make_case(4, 300)
        result = attack.known_plaintext_attack(cipher, plain[:7], 12, (2, 20))
        self.assertEqual(result.status, "partial")
        self.assertIsNone(result.plaintext)
        self.assertEqual(result.selected.keyword.count("?"), 5)
        # k < m gives no way to tell rail counts apart: all 19 survive, the true one among them
        self.assertEqual(len(result.consistent), 19)
        true_candidate = next(c for c in result.consistent if c.rails == rails)
        self.assertEqual(true_candidate.keyword[:7], keyword[:7])

    def test_incorrect_known_plaintext_fails(self):
        plain, _, _, cipher = make_case(6, 300)
        wrong = sample_data.generate_random_letters(30, sample_data.make_rng(99))
        result = attack.known_plaintext_attack(cipher, wrong, 12, (2, 20))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.consistent, [])

    def test_rails_outside_search_range_fails(self):
        plain, _, _, cipher = make_case(7, 300, rails=15)
        result = attack.known_plaintext_attack(cipher, plain[:30], 12, (2, 10))
        self.assertEqual(result.status, "failed")

    def test_wrong_assumed_key_length_fails(self):
        plain, _, _, cipher = make_case(8, 300)
        result = attack.known_plaintext_attack(cipher, plain[:40], 11, (2, 20))
        self.assertEqual(result.status, "failed")

    def test_unknown_key_length_range(self):
        plain, keyword, rails, cipher = make_case(10, 400)
        result = attack.known_plaintext_attack(cipher, plain[:40], range(10, 16), (2, 20))
        self.assertEqual((result.selected.rails, result.selected.keyword), (rails, keyword))
        self.assertEqual(result.candidates_tested, 19 * 6)

    def test_known_segment_in_the_middle(self):
        plain, keyword, rails, cipher = make_case(11, 300)
        result = attack.known_plaintext_attack(cipher, plain[50:80], 12, (2, 20), known_offset=50)
        self.assertEqual(result.plaintext, plain)

    def test_short_message_attack(self):
        rng = sample_data.make_rng(1)
        plain = sample_data.generate_english_text(50, rng)
        cipher = hybrid_cipher.encrypt(plain, KEY, 6)
        result = attack.known_plaintext_attack(cipher, plain[:24], 12, (2, 20))
        self.assertEqual(result.plaintext, plain)

    def test_invalid_attack_inputs(self):
        with self.assertRaises(ValidationError):
            attack.known_plaintext_attack("ABC", "ABCDEF", 12)           # segment longer than ciphertext
        with self.assertRaises(ValidationError):
            attack.known_plaintext_attack("", "ABC", 12)                  # empty ciphertext
        with self.assertRaises(ValidationError):
            attack.known_plaintext_attack("ABCDEFGHIJ", "", 12)           # empty known text
        with self.assertRaises(ValidationError):
            attack.known_plaintext_attack("ABCDEFGHIJ", "ABC", 12, known_offset=9)
        with self.assertRaises(ValidationError):
            attack.known_plaintext_attack("ABCDEFGHIJ", "ABC", 0)
        with self.assertRaises(ValidationError):
            attack.known_plaintext_attack("ABCDEFGHIJ", "ABC", 12, rail_range=(8, 3))

    def test_effort_is_reported_and_scales_with_length(self):
        small = make_case(12, 100)
        large = make_case(12, 1000)
        r1 = attack.known_plaintext_attack(small[3], small[0][:24], 12, (2, 20))
        r2 = attack.known_plaintext_attack(large[3], large[0][:24], 12, (2, 20))
        self.assertGreater(r2.char_operations, r1.char_operations)
        self.assertEqual(r1.candidates_tested, 19)

    def test_derivation_table_matches_modular_arithmetic(self):
        plain, keyword, rails, cipher = make_case(13, 100)
        table = attack.derivation_table(cipher, plain[:5], rails, 12)
        self.assertEqual("".join(row[4] for row in table), keyword[:5])


class TestCiphertextOnlyAttack(unittest.TestCase):
    def test_recovers_keys_from_long_ciphertext(self):
        plain, keyword, rails, cipher = make_case(21, 2000)
        result = attack.ciphertext_only_attack(cipher, 12, (2, 20))
        self.assertEqual((result.rails, result.keyword, result.plaintext), (rails, keyword, plain))


class TestFrequencyAnalysis(unittest.TestCase):
    def test_frequencies_sum_to_one(self):
        self.assertAlmostEqual(sum(fa.letter_frequencies("HELLOWORLD")), 1.0)
        self.assertAlmostEqual(sum(fa.ENGLISH_FREQ), 1.0)

    def test_empty_text(self):
        self.assertEqual(sum(fa.letter_counts("")), 0)
        self.assertEqual(fa.index_of_coincidence("A"), 0.0)

    def test_ic_of_english_vs_random(self):
        rng = sample_data.make_rng(3)
        self.assertGreater(fa.index_of_coincidence(sample_data.generate_english_text(2000, rng)), 0.06)
        self.assertLess(fa.index_of_coincidence(sample_data.generate_random_letters(5000, rng)), 0.045)

    def test_shift_cipher_broken_by_frequency(self):
        plain = sample_data.generate_english_text(400, sample_data.make_rng(4))
        for key in (0, 1, 13, 25):
            best, _ = fa.break_shift_by_frequency(shift_cipher.encrypt(plain, key))
            self.assertEqual(best, key)

    def test_hcc_flattens_frequencies(self):
        plain = sample_data.generate_english_text(2000, sample_data.make_rng(5))
        cipher = hybrid_cipher.encrypt(plain, KEY, 4)
        self.assertLess(fa.index_of_coincidence(cipher), 0.05)
        best, _ = fa.break_shift_by_frequency(cipher)
        self.assertNotEqual(shift_cipher.decrypt(cipher, best), plain)

    def test_report_runs(self):
        self.assertIn("Index of coincidence", fa.frequency_report("HELLOWORLD"))


class TestPerformance(unittest.TestCase):
    def test_small_benchmark_runs(self):
        rows = performance.benchmark_ciphers([50, 200], trials=2, attack_trials=1)
        self.assertEqual([r["length"] for r in rows], [50, 200])
        self.assertTrue(all(r["hcc_encrypt_s"] > 0 for r in rows))

    def test_small_attack_experiment_is_reproducible(self):
        first = performance.attack_success_experiment([100], [16], trials=5)
        second = performance.attack_success_experiment([100], [16], trials=5)
        self.assertEqual(first[0]["strict_pct"], second[0]["strict_pct"])
        self.assertEqual(first[0]["ranked_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
