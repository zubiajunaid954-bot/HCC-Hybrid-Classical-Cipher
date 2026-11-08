"""Tests for the individual ciphers, HCC encryption/decryption and input validation."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_cipher
import rail_fence
import shift_cipher
import vigenere
from utils import ValidationError, normalize_text, smallest_period, validate_keyword, validate_rails

KEY = "SECURITYKEYS"           # 12 letters


class TestNormalization(unittest.TestCase):
    def test_uppercase_and_strip(self):
        self.assertEqual(normalize_text("Hello, World! 123 \n"), "HELLOWORLD")

    def test_non_ascii_removed(self):
        self.assertEqual(normalize_text("café naïve"), "CAFNAVE")

    def test_non_string_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_text(None)


class TestKnownVectors(unittest.TestCase):
    def test_vigenere_textbook_vector(self):
        # Classic example (short key, so call the internal routine directly).
        self.assertEqual(vigenere._shift_text("ATTACKATDAWN", "LEMON", +1), "LXFOPVEFRNHR")

    def test_rail_fence_textbook_vector(self):
        self.assertEqual(rail_fence.encrypt("WEAREDISCOVEREDFLEEATONCE", 3), "WECRLTEERDSOEEFEAOCAIVDEN")

    def test_shift_vector(self):
        self.assertEqual(shift_cipher.encrypt("HELLO", 3), "KHOOR")
        self.assertEqual(shift_cipher.decrypt("KHOOR", 3), "HELLO")

    def test_hcc_manual_pipeline(self):
        plain = "ATTACKATDAWNATTACK"
        stage1 = vigenere.encrypt(plain, KEY)
        self.assertEqual(hybrid_cipher.encrypt(plain, KEY, 4), rail_fence.encrypt(stage1, 4))


class TestWorkedExamples(unittest.TestCase):
    """The report's worked example (demo keyword, 4 rails), checked by hand letter by letter."""

    PLAIN = "MEETMEATTHELIBRARYTOMORROW"
    STAGE1 = "EIGNDMTRDLCDAFTUIGMMWSPJGA"      # e.g. M + S = 12 + 18 = 30 -> 4 = E
    CIPHER = "ETAMGIMRDFGMJAGDDCTIWPNLUS"      # rail 1 holds positions 0, 6, 12, 18, 24 -> E T A M G

    def test_stage1_by_hand(self):
        self.assertEqual(vigenere.encrypt("Meet me at the library tomorrow", KEY), self.STAGE1)

    def test_stage2_by_hand(self):
        self.assertEqual(rail_fence.encrypt(self.STAGE1, 4), self.CIPHER)

    def test_both_stages(self):
        self.assertEqual(hybrid_cipher.encrypt("Meet me at the library tomorrow", KEY, 4), self.CIPHER)

    def test_decryption_reverses_both_stages(self):
        self.assertEqual(rail_fence.decrypt(self.CIPHER, 4), self.STAGE1)
        self.assertEqual(hybrid_cipher.decrypt(self.CIPHER, KEY, 4), self.PLAIN)


class TestRoundTrips(unittest.TestCase):
    def test_every_short_length_and_many_rails(self):
        rng = random.Random(1)
        for length in range(1, 80):
            plain = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(length))
            for rails in range(2, 12):
                with self.subTest(length=length, rails=rails):
                    self.assertEqual(hybrid_cipher.decrypt(hybrid_cipher.encrypt(plain, KEY, rails), KEY, rails), plain)

    def test_message_shorter_than_key(self):
        self.assertEqual(hybrid_cipher.decrypt(hybrid_cipher.encrypt("HI", KEY, 3), KEY, 3), "HI")

    def test_message_exactly_key_length(self):
        plain = "ABCDEFGHIJKL"
        self.assertEqual(hybrid_cipher.decrypt(hybrid_cipher.encrypt(plain, KEY, 5), KEY, 5), plain)

    def test_long_message(self):
        rng = random.Random(2)
        plain = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(10000))
        self.assertEqual(hybrid_cipher.decrypt(hybrid_cipher.encrypt(plain, KEY, 7), KEY, 7), plain)

    def test_rails_larger_than_message(self):
        plain = "SHORT"
        self.assertEqual(hybrid_cipher.decrypt(hybrid_cipher.encrypt(plain, KEY, 50), KEY, 50), plain)

    def test_repeated_letters(self):
        plain = "A" * 40
        cipher = hybrid_cipher.encrypt(plain, KEY, 4)
        self.assertEqual(hybrid_cipher.decrypt(cipher, KEY, 4), plain)

    def test_formatted_input_decrypts_to_normalized_plaintext(self):
        message = "Meet me, at 9 o'clock!"
        cipher = hybrid_cipher.encrypt(message, KEY.lower(), 3)
        self.assertEqual(hybrid_cipher.decrypt(cipher, KEY, 3), normalize_text(message))

    def test_ciphertext_is_letters_of_same_length(self):
        cipher = hybrid_cipher.encrypt("ATTACKATDAWN", KEY, 3)
        self.assertEqual(len(cipher), 12)
        self.assertTrue(cipher.isalpha() and cipher.isupper())

    def test_wrong_key_does_not_decrypt(self):
        plain = "THISISASECRETMESSAGE"
        cipher = hybrid_cipher.encrypt(plain, KEY, 4)
        self.assertNotEqual(hybrid_cipher.decrypt(cipher, "ANOTHERKEYWORD", 4), plain)
        self.assertNotEqual(hybrid_cipher.decrypt(cipher, KEY, 5), plain)

    def test_stage_order_matters(self):
        plain = "THISISASECRETMESSAGE"
        reversed_order = vigenere.encrypt(rail_fence.encrypt(plain, 4), KEY)
        self.assertNotEqual(reversed_order, hybrid_cipher.encrypt(plain, KEY, 4))

    def test_rail_fence_preserves_letter_multiset(self):
        text = "HELLOWORLDTHISISATEST"
        self.assertEqual(sorted(rail_fence.encrypt(text, 5)), sorted(text))

    def test_shift_roundtrip_all_keys(self):
        for key in range(-30, 60):
            self.assertEqual(shift_cipher.decrypt(shift_cipher.encrypt("ZEBRA", key), key), "ZEBRA")


class TestValidation(unittest.TestCase):
    def test_empty_inputs(self):
        for bad in ("", "   ", "123 !?"):
            with self.subTest(text=bad):
                with self.assertRaises(ValidationError):
                    hybrid_cipher.encrypt(bad, KEY, 3)
                with self.assertRaises(ValidationError):
                    hybrid_cipher.decrypt(bad, KEY, 3)

    def test_short_keyword_rejected(self):
        with self.assertRaises(ValidationError):
            validate_keyword("SHORTKEY")          # 8 letters
        self.assertEqual(validate_keyword("abcdefghij"), "ABCDEFGHIJ")  # exactly 10 is fine

    def test_keyword_with_non_letters_rejected(self):
        for bad in ("SECURITY KEYS", "SECURITYKEY5", "SECURITY-KEYS", "", None, 123):
            with self.subTest(keyword=bad):
                with self.assertRaises(ValidationError):
                    validate_keyword(bad)

    def test_periodic_keyword_rejected(self):
        for bad in ("AAAAAAAAAAAA", "ABCABCABCABC", "ABABABABABAB"):
            with self.subTest(keyword=bad):
                with self.assertRaises(ValidationError):
                    validate_keyword(bad)
        self.assertEqual(smallest_period("SECURITYKEYS"), 12)

    def test_invalid_rails(self):
        for bad in (1, 0, -4, "x", None, 2.5, True, [3]):
            with self.subTest(rails=bad):
                with self.assertRaises(ValidationError):
                    validate_rails(bad)
        self.assertEqual(validate_rails("4"), 4)

    def test_invalid_shift(self):
        with self.assertRaises(ValidationError):
            shift_cipher.encrypt("HELLO", "3")


if __name__ == "__main__":
    unittest.main()
