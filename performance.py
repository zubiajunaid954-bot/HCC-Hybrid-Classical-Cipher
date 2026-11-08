"""Measured (never invented) performance and attack-success experiments.

Everything here is produced by running the real code with time.perf_counter()
and seeded random generators, so results are reproducible in method; absolute
times naturally depend on the machine.

The experiments are started from the web interface (Performance section,
"Run full experiments and save"); this module has no command-line entry point.
"""

import csv
import os
import statistics
import time

import attack
import hybrid_cipher
import sample_data
import shift_cipher

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
TIMING_LENGTHS = [50, 100, 500, 1000, 5000, 10000]
ATTACK_LENGTHS = [50, 100, 500, 1000]
SEGMENT_SIZES = [8, 12, 13, 14, 16, 24]
KEY_LENGTH = 12
RAIL_RANGE = (2, 20)
TIMING_KNOWN_SEGMENT = 36        # known-plaintext size used in the timing table


def time_calls(function, trials):
    """Run `function()` once untimed (warm-up) and `trials` times timed.
    Returns (mean_seconds, min_seconds, stdev_seconds)."""
    function()
    samples = []
    for _ in range(trials):
        start = time.perf_counter()
        function()
        samples.append(time.perf_counter() - start)
    spread = statistics.stdev(samples) if len(samples) > 1 else 0.0
    return statistics.fmean(samples), min(samples), spread


def benchmark_ciphers(lengths=TIMING_LENGTHS, trials=30, attack_trials=10, seed=2024):
    """Time HCC and Shift encryption/decryption plus the known-plaintext attack."""
    rng = sample_data.make_rng(seed)
    keyword = sample_data.DEFAULT_KEYWORD
    rails, shift = sample_data.DEFAULT_RAILS, 7
    rows = []
    for n in lengths:
        plaintext = sample_data.generate_english_text(n, rng)
        hcc_cipher = hybrid_cipher.encrypt(plaintext, keyword, rails)
        shift_cipher_text = shift_cipher.encrypt(plaintext, shift)
        known = plaintext[:min(TIMING_KNOWN_SEGMENT, n)]
        hcc_enc = time_calls(lambda: hybrid_cipher.encrypt(plaintext, keyword, rails), trials)[0]
        hcc_dec = time_calls(lambda: hybrid_cipher.decrypt(hcc_cipher, keyword, rails), trials)[0]
        sh_enc = time_calls(lambda: shift_cipher.encrypt(plaintext, shift), trials)[0]
        sh_dec = time_calls(lambda: shift_cipher.decrypt(shift_cipher_text, shift), trials)[0]
        atk = time_calls(lambda: attack.known_plaintext_attack(
            hcc_cipher, known, KEY_LENGTH, RAIL_RANGE), attack_trials)[0]
        rows.append({"length": n, "hcc_encrypt_s": hcc_enc, "hcc_decrypt_s": hcc_dec,
                     "shift_encrypt_s": sh_enc, "shift_decrypt_s": sh_dec, "attack_s": atk})
    return rows


def attack_success_experiment(lengths=ATTACK_LENGTHS, segment_sizes=SEGMENT_SIZES,
                              trials=200, seed=7):
    """Known-plaintext attack success rate and effort.

    Conditions: random 12-letter keyword (not periodic), random rails in [2, 20],
    English-like plaintext, known segment = first k letters (offset 0), attacker
    told key length 12 and rail range 2..20.  Same seed => identical trials.

    strict_%  : exactly one hypothesis survived and it was the true (rails, keyword).
                (consistency test only - no language knowledge used)
    ranked_%  : the final answer (consistent hypotheses ranked by English-likeness)
                had the true rails, keyword and recovered the full plaintext.
    """
    rows = []
    for n in lengths:
        for k in segment_sizes:
            if k > n:
                continue
            rng = sample_data.make_rng(f"{seed}-{n}-{k}")
            strict = ranked = 0
            survivors, operations, tested, elapsed = [], [], [], []
            for _ in range(trials):
                keyword = sample_data.generate_random_keyword(KEY_LENGTH, rng)
                rails = rng.randint(RAIL_RANGE[0], min(RAIL_RANGE[1], n))
                plaintext = sample_data.generate_english_text(n, rng)
                ciphertext = hybrid_cipher.encrypt(plaintext, keyword, rails)
                result = attack.known_plaintext_attack(ciphertext, plaintext[:k], KEY_LENGTH,
                                                       RAIL_RANGE)
                survivors.append(len(result.consistent))
                operations.append(result.char_operations)
                tested.append(result.candidates_tested)
                elapsed.append(result.elapsed_seconds)
                correct = (result.status == "recovered" and result.selected.rails == rails
                           and result.selected.keyword == keyword and result.plaintext == plaintext)
                ranked += correct
                strict += correct and len(result.consistent) == 1
            rows.append({"length": n, "known_k": k, "trials": trials,
                         "strict_pct": 100 * strict / trials, "ranked_pct": 100 * ranked / trials,
                         "avg_survivors": statistics.fmean(survivors),
                         "candidates_tested": statistics.fmean(tested),
                         "avg_char_ops": statistics.fmean(operations),
                         "avg_time_s": statistics.fmean(elapsed)})
    return rows


def ciphertext_only_experiment(lengths=(100, 250, 500, 1000, 2000, 4000), trials=40, seed=11):
    """Bonus: success rate of the ciphertext-only (frequency) attack vs ciphertext length."""
    rows = []
    for n in lengths:
        rng = sample_data.make_rng(f"coa-{seed}-{n}")
        wins, elapsed, operations = 0, [], []
        for _ in range(trials):
            keyword = sample_data.generate_random_keyword(KEY_LENGTH, rng)
            rails = rng.randint(*RAIL_RANGE)
            plaintext = sample_data.generate_english_text(n, rng)
            ciphertext = hybrid_cipher.encrypt(plaintext, keyword, rails)
            result = attack.ciphertext_only_attack(ciphertext, KEY_LENGTH, RAIL_RANGE)
            wins += result.plaintext == plaintext
            elapsed.append(result.elapsed_seconds)
            operations.append(result.char_operations)
        rows.append({"length": n, "trials": trials, "full_recovery_pct": 100 * wins / trials,
                     "avg_char_ops": statistics.fmean(operations),
                     "avg_time_s": statistics.fmean(elapsed)})
    return rows


# ------------------------------- output helpers -------------------------------

def _ms(seconds):
    return f"{seconds * 1000:.4f}"


def format_timing_table(rows):
    header = (f"{'Length':>7} | {'HCC enc':>10} | {'HCC dec':>10} | {'Shift enc':>10} | "
              f"{'Shift dec':>10} | {'KPA attack':>11} | {'HCC/Shift enc':>13}")
    lines = ["All times in milliseconds (mean of repeated trials)", header, "-" * len(header)]
    for r in rows:
        ratio = r["hcc_encrypt_s"] / r["shift_encrypt_s"]
        lines.append(f"{r['length']:>7} | {_ms(r['hcc_encrypt_s']):>10} | {_ms(r['hcc_decrypt_s']):>10} | "
                     f"{_ms(r['shift_encrypt_s']):>10} | {_ms(r['shift_decrypt_s']):>10} | "
                     f"{_ms(r['attack_s']):>11} | {ratio:>12.2f}x")
    if len(rows) >= 2 and rows[0]["length"] != rows[-1]["length"]:
        first, last = rows[0], rows[-1]
        lines.append(f"\nScaling check: length x{last['length'] / first['length']:.0f} -> HCC encryption "
                     f"time x{last['hcc_encrypt_s'] / first['hcc_encrypt_s']:.1f} (linear growth = O(n)).")
    return "\n".join(lines)


def format_attack_table(rows):
    header = (f"{'Ct len':>6} {'Known k':>8} {'Trials':>7} {'Strict %':>9} {'Ranked %':>9} "
              f"{'Survivors':>10} {'Tested':>7} {'Char ops':>9} {'Time ms':>9}")
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(f"{r['length']:>6} {r['known_k']:>8} {r['trials']:>7} {r['strict_pct']:>9.1f} "
                     f"{r['ranked_pct']:>9.1f} {r['avg_survivors']:>10.2f} "
                     f"{r['candidates_tested']:>7.0f} {r['avg_char_ops']:>9.0f} "
                     f"{_ms(r['avg_time_s']):>9}")
    return "\n".join(lines)


def format_coa_table(rows):
    header = f"{'Ct len':>7} {'Trials':>7} {'Full recovery %':>16} {'Char ops':>10} {'Time ms':>9}"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(f"{r['length']:>7} {r['trials']:>7} {r['full_recovery_pct']:>16.1f} "
                     f"{r['avg_char_ops']:>10.0f} {_ms(r['avg_time_s']):>9}")
    return "\n".join(lines)


def save_csv(rows, filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def save_graphs(timing_rows, attack_rows):
    """Write PNG graphs with matplotlib if installed; return list of paths (or [])."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    os.makedirs(RESULTS_DIR, exist_ok=True)
    paths = []

    lengths = [r["length"] for r in timing_rows]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for key, label, style in [("hcc_encrypt_s", "HCC encrypt", "o-"), ("hcc_decrypt_s", "HCC decrypt", "s-"),
                              ("shift_encrypt_s", "Shift encrypt", "^--"), ("shift_decrypt_s", "Shift decrypt", "v--")]:
        axes[0].plot(lengths, [r[key] * 1000 for r in timing_rows], style, label=label)
    axes[0].set(xscale="log", yscale="log", xlabel="Message length (letters)", ylabel="Mean time (ms)",
                title="Encryption / decryption time")
    axes[1].plot(lengths, [r["attack_s"] * 1000 for r in timing_rows], "d-", color="firebrick")
    axes[1].set(xscale="log", yscale="log", xlabel="Ciphertext length (letters)", ylabel="Mean time (ms)",
                title=f"Known-plaintext attack (rails {RAIL_RANGE[0]}-{RAIL_RANGE[1]})")
    for ax in axes:
        ax.grid(True, which="both", alpha=0.3)
    axes[0].legend()
    fig.tight_layout()
    paths.append(os.path.join(RESULTS_DIR, "timing.png"))
    fig.savefig(paths[-1], dpi=150)
    plt.close(fig)

    if attack_rows:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        for n in sorted({r["length"] for r in attack_rows}):
            subset = [r for r in attack_rows if r["length"] == n]
            axes[0].plot([r["known_k"] for r in subset], [r["strict_pct"] for r in subset], "o-", label=f"n={n}")
            axes[1].plot([r["known_k"] for r in subset], [r["ranked_pct"] for r in subset], "o-", label=f"n={n}")
        axes[0].set(title="Strict success (unique consistent hypothesis)")
        axes[1].set(title="Success with English-likeness ranking")
        for ax in axes:
            ax.axvline(KEY_LENGTH, color="grey", linestyle=":")
            ax.set(xlabel="Known plaintext length k (key length m = 12 dotted)", ylabel="Success rate (%)",
                   ylim=(-2, 102))
            ax.grid(True, alpha=0.3)
            ax.legend()
        fig.tight_layout()
        paths.append(os.path.join(RESULTS_DIR, "attack_success.png"))
        fig.savefig(paths[-1], dpi=150)
        plt.close(fig)
    return paths


def run_all(quick=False, output=print):
    """Run every experiment, print tables, save CSV/PNG. Returns the data dictionary."""
    if quick:
        timing = benchmark_ciphers([50, 500, 5000], trials=5, attack_trials=3)
        attacks = attack_success_experiment([100, 500], [8, 12, 13, 16], trials=30)
        coa = ciphertext_only_experiment((500, 2000), trials=5)
    else:
        timing = benchmark_ciphers()
        attacks = attack_success_experiment()
        coa = ciphertext_only_experiment()
    output("\n=== 1. Encryption / decryption / attack timing ===")
    output(format_timing_table(timing))
    output("\n=== 2. Known-plaintext attack: success rate and effort ===")
    output(format_attack_table(attacks))
    output("\n=== 3. Bonus: ciphertext-only (frequency) attack ===")
    output(format_coa_table(coa))
    if not quick:
        files = [save_csv(timing, "timing.csv"), save_csv(attacks, "attack_success.csv"),
                 save_csv(coa, "ciphertext_only.csv")] + save_graphs(timing, attacks)
        output("\nSaved: " + ", ".join(os.path.relpath(p) for p in files))
    return {"timing": timing, "attack": attacks, "ciphertext_only": coa}
