"""Reproducible sample data for demos, tests and experiments.

SENTENCES is a small original English corpus.  `generate_english_text` builds
plaintexts of any length by joining randomly chosen sentences, so letter
statistics resemble ordinary English while the experiments stay reproducible
(a seeded random.Random is always passed in).
"""

import random

from utils import ALPHABET, normalize_text

DEFAULT_KEYWORD = "SECURITYKEYS"      # 12 letters, fixed demo configuration
DEFAULT_RAILS = 4
DEFAULT_MESSAGE = "Meet me at the library tomorrow morning before the network security lecture begins."

SENTENCES = [
    "The students gathered in the laboratory to study how classical ciphers protected secret messages long before computers existed.",
    "A good cryptographer always assumes that the enemy knows the system and that only the key remains secret.",
    "Substitution replaces each letter with another symbol while transposition simply changes the order of the letters.",
    "When the weather turned cold the travellers decided to wait inside the old station until the morning train arrived.",
    "Frequency analysis works because every language uses some letters far more often than others in ordinary writing.",
    "The engineer carefully measured the time that each program needed to process messages of different lengths.",
    "Nobody expected the small library at the end of the street to hold such a remarkable collection of ancient manuscripts.",
    "She wrote a short report explaining why the new design was easier to understand and cheaper to maintain than the old one.",
    "Many early encryption machines combined several simple operations because a single step was too easy to reverse.",
    "The committee reviewed every proposal during the meeting and then agreed to continue the discussion on the following day.",
    "A reliable network depends on careful planning, regular testing and clear communication between all the people involved.",
    "Late in the evening the harbour became quiet and only the sound of the water against the wooden boats remained.",
    "To recover the hidden key the analyst compared a known piece of text with the matching piece of the encrypted message.",
    "Modern systems rely on public standards that have been examined by thousands of experts around the world.",
    "The teacher asked everyone to explain the algorithm in their own words before running the program on the computer.",
    "Rivers carry water from the mountains to the sea and many great cities were built along their banks.",
    "Although the experiment looked simple, repeating it many times was necessary to obtain results that could be trusted.",
    "The museum displayed letters that soldiers had written and sealed with wax during the long winter of the war.",
    "Every additional layer of protection should be justified by a clear improvement in security rather than by complexity alone.",
    "On Saturday the whole family travelled to the village where their grandmother had spent most of her childhood.",
    "Careful documentation allows another person to repeat the work, check the conclusions and discover any mistakes.",
    "The merchant stored his records in a locked wooden chest and shared the only key with his most trusted assistant.",
    "Computers perform millions of simple operations every second, which makes searching through small key spaces completely practical.",
    "An attacker who obtains a few words of the original message can often learn a surprising amount about the key.",
    "During the summer the garden produced more vegetables than the neighbours could eat, so the extra food was shared.",
    "The professor reminded the class that a cipher is not secure simply because its inventor cannot find a way to break it.",
    "Several volunteers helped to repair the bridge, and by the end of the week people could cross the river again.",
    "Testing a program with unusual input is the best way to find the errors that ordinary examples never reveal.",
    "The pilot checked the instruments one more time, confirmed the route with the tower and prepared for departure.",
    "Reading old books about mathematics and codes taught him that patient observation often beats clever guessing.",
    "Strong passwords, regular updates and careful backups protect ordinary users against the most common digital threats.",
    "The detective noticed that the letters of the strange note repeated in a pattern that suggested a hidden keyword.",
]


def generate_english_text(length, rng):
    """Return exactly `length` uppercase letters of English-like text (A-Z only)."""
    letters = ""
    while len(letters) < length:
        letters += normalize_text(rng.choice(SENTENCES))
    return letters[:length]


def generate_random_letters(length, rng):
    """Uniformly random A-Z text (no language statistics at all)."""
    return "".join(rng.choice(ALPHABET) for _ in range(length))


def generate_random_keyword(length, rng):
    """Random keyword of `length` letters that is not a repetition of a shorter word."""
    from utils import validate_keyword

    while True:
        candidate = generate_random_letters(length, rng)
        try:
            return validate_keyword(candidate, min_length=min(length, 10))
        except ValueError:
            continue


def make_rng(seed):
    """Seeded random generator so experiments can be repeated exactly."""
    return random.Random(seed)
