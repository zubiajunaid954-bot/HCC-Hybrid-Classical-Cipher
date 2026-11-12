"""Tests for the web interface's JSON API (app.py). They call the handler
functions directly, so no server or browser is needed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402
import hybrid_cipher  # noqa: E402
from utils import ValidationError  # noqa: E402


class TestWebApi(unittest.TestCase):
    def test_encrypt_then_decrypt_round_trip(self):
        enc = app.api_encrypt({"plaintext": "Meet me at nine!", "keyword": "SECURITYKEYS", "rails": 3})
        self.assertEqual(enc["output"], hybrid_cipher.encrypt("MEETMEATNINE", "SECURITYKEYS", 3))
        self.assertEqual(enc["removed"], 4)
        self.assertEqual(len(enc["pattern"]), len(enc["stage1"]))
        dec = app.api_decrypt({"ciphertext": enc["output"], "keyword": "SECURITYKEYS", "rails": 3})
        self.assertEqual(dec["output"], "MEETMEATNINE")

    def test_invalid_keys_are_rejected(self):
        with self.assertRaises(ValidationError):
            app.api_encrypt({"plaintext": "HELLO", "keyword": "SHORT", "rails": 3})
        with self.assertRaises(ValidationError):
            app.api_encrypt({"plaintext": "HELLO", "keyword": "SECURITYKEYS", "rails": 1})

    def test_known_plaintext_attack_endpoint(self):
        plain = "THEQUICKBROWNFOXJUMPSOVERTHELAZYDOGANDKEEPSRUNNING"
        cipher = hybrid_cipher.encrypt(plain, "SECURITYKEYS", 5)
        r = app.api_attack_known({"ciphertext": cipher, "known": plain[:18], "keyLengths": "12",
                                  "railMin": 2, "railMax": 20, "original": plain})
        self.assertEqual(r["status"], "recovered")
        self.assertEqual(r["selected"]["rails"], 5)
        self.assertEqual(r["selected"]["keyword"], "SECURITYKEYS")
        self.assertTrue(r["verified"])
        self.assertTrue(r["matchesOriginal"])

    def test_attack_working_matches_the_search_log(self):
        plain = "MEETMEATTHELIBRARYTOMORROW"
        cipher = hybrid_cipher.encrypt(plain, "SECURITYKEYS", 4)
        r = app.api_attack_known({"ciphertext": cipher, "known": plain[:16], "keyLengths": "12",
                                  "railMin": 2, "railMax": 8, "original": plain})
        guesses = r["working"]["guesses"]
        self.assertEqual([g["rails"] for g in guesses], [t["rails"] for t in r["trace"]])
        for g, t in zip(guesses, r["trace"]):
            self.assertEqual(g["keyword"], t["key"])
            self.assertEqual(g["conflicts"], t["conflicts"])
            self.assertEqual(sum(l["status"] == "conflict" for l in g["letters"]), t["conflicts"])
        right = next(g for g in guesses if g["rails"] == 4)
        self.assertTrue(right["consistent"])
        self.assertEqual(right["stage1"], "EIGNDMTRDLCDAFTUIGMMWSPJGA")   # the true Stage 1 text

    def test_attack_working_only_for_short_ciphertexts(self):
        plain = "THEQUICKBROWNFOXJUMPSOVERTHELAZYDOG" * 5
        cipher = hybrid_cipher.encrypt(plain, "SECURITYKEYS", 5)
        r = app.api_attack_known({"ciphertext": cipher, "known": plain[:20], "keyLengths": "12"})
        self.assertIsNone(r["working"])

    def test_key_length_range_parsing(self):
        self.assertEqual(app._int_list("10-12,15", "Key length"), [10, 11, 12, 15])
        with self.assertRaises(ValidationError):
            app._int_list("14-10", "Key length")

    def test_frequency_and_compare(self):
        f = app.api_frequency({"text": "HELLO WORLD"})
        self.assertEqual(f["length"], 10)
        c = app.api_compare({"length": 300, "shift": 11})
        self.assertTrue(c["rows"][1]["frequencyAttackRecovers"])
        self.assertFalse(c["rows"][2]["frequencyAttackRecovers"])


if __name__ == "__main__":
    unittest.main()
