"""Stage 2 - Rail Fence cipher (zig-zag transposition).

The plaintext is written diagonally on `rails` rows (down, then up, ...) and
read off row by row.  Letters are only moved, never changed, so letter
frequencies are preserved.  Time O(n), space O(n).
"""

from utils import require_message, validate_rails


def rail_pattern(length, rails):
    """Return, for every position 0..length-1, the rail (row) it is written on.

    The zig-zag repeats every 2*(rails-1) positions: 0,1,...,rails-1,rails-2,...,1
    """
    cycle = 2 * (rails - 1)
    pattern = []
    for i in range(length):
        position = i % cycle
        pattern.append(position if position < rails else cycle - position)
    return pattern


def rail_order(length, rails):
    """Positions in the order they are read off: rail 0 first, then rail 1, ...

    `ciphertext[j] = plaintext[order[j]]` - this permutation is the whole cipher.
    """
    buckets = [[] for _ in range(rails)]
    for position, rail in enumerate(rail_pattern(length, rails)):
        buckets[rail].append(position)
    return [position for bucket in buckets for position in bucket]


def encrypt(text, rails):
    """Rail-Fence-encrypt `text` using `rails` rails."""
    text = require_message(text)
    rails = validate_rails(rails)
    return "".join(text[position] for position in rail_order(len(text), rails))


def decrypt(ciphertext, rails):
    """Invert the zig-zag: put each ciphertext letter back where it came from."""
    ciphertext = require_message(ciphertext, "ciphertext")
    rails = validate_rails(rails)
    restored = [""] * len(ciphertext)
    for letter, position in zip(ciphertext, rail_order(len(ciphertext), rails)):
        restored[position] = letter
    return "".join(restored)


def draw_fence(text, rails):
    """Return a printable zig-zag diagram (used in the CLI and the report)."""
    text = require_message(text)
    rails = validate_rails(rails)
    grid = [["."] * len(text) for _ in range(rails)]
    for position, rail in enumerate(rail_pattern(len(text), rails)):
        grid[rail][position] = text[position]
    return "\n".join(" ".join(row) for row in grid)
