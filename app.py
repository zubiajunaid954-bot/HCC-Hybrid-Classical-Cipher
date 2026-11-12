"""HCC Workbench - web user interface for the Hybrid Classical Cipher.

Runs a small local web server (Python standard library only, no Flask needed)
that serves the interface in ./ui and exposes the project's real modules as a
JSON API.  This is the only way to run the project: every action (encryption,
decryption, step-by-step walkthrough, attacks, frequency analysis and the
performance experiments) is started from the browser, and every number shown
there is computed by the same Python modules the unit tests check.

    python app.py                 # opens http://127.0.0.1:8000 in your browser
    python app.py --port 8080     # use another port
    python app.py --no-browser    # do not open a browser tab automatically
"""

import argparse
import csv
import json
import math
import os
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import attack
import frequency_analysis as fa
import hybrid_cipher
import performance
import rail_fence
import sample_data
import shift_cipher
from utils import (MIN_KEYWORD_LENGTH, ValidationError, normalize_text, require_message,
                   validate_keyword, validate_rails)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "ui")
MAX_TEXT = 200_000            # letters accepted by the API (keeps the demo responsive)
WORKING_LIMIT = 120           # longest text shown step by step in the interface


# --------------------------------------------------------------------- helpers

def _int(value, name, low=None, high=None):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a whole number.") from None
    if low is not None and number < low:
        raise ValidationError(f"{name} must be at least {low}.")
    if high is not None and number > high:
        raise ValidationError(f"{name} must be at most {high}.")
    return number


def _int_list(value, name, low=1, high=100_000, limit=12):
    """Parse '12', '10-14' or '50, 100, 500' into a sorted list of ints."""
    if isinstance(value, list):
        parts = [str(v) for v in value]
    else:
        parts = [p for p in str(value).replace(" ", "").split(",") if p]
    numbers = set()
    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = _int(a, name, low, high), _int(b, name, low, high)
            if b < a:
                raise ValidationError(f"{name}: range {part} is reversed.")
            numbers.update(range(a, b + 1))
        else:
            numbers.add(_int(part, name, low, high))
    if not numbers:
        raise ValidationError(f"Enter at least one value for {name}.")
    if len(numbers) > limit:
        raise ValidationError(f"{name}: at most {limit} values at a time.")
    return sorted(numbers)


def _text(payload, key, what):
    text = require_message(payload.get(key, ""), what)
    if len(text) > MAX_TEXT:
        raise ValidationError(f"The {what} is too long for the interface ({len(text):,} letters, "
                              f"limit {MAX_TEXT:,}).")
    return text


def _freq_summary(text):
    counts = fa.letter_counts(text)
    total = sum(counts)
    return {
        "length": total,
        "counts": counts,
        "percent": [100 * c / total if total else 0 for c in counts],
        "ic": fa.index_of_coincidence(text),
        "chi2": fa.chi_squared(text),
    }


# ------------------------------------------------------------------- endpoints

def api_defaults(_):
    rng = sample_data.make_rng(5)
    return {
        "keyword": sample_data.DEFAULT_KEYWORD,
        "rails": sample_data.DEFAULT_RAILS,
        "message": sample_data.DEFAULT_MESSAGE,
        "minKeyword": MIN_KEYWORD_LENGTH,
        "englishPercent": fa.ENGLISH_PERCENT,
        "icEnglish": fa.IC_ENGLISH,
        "icRandom": fa.IC_RANDOM,
        "longSample": sample_data.generate_english_text(600, rng),
    }


def api_encrypt(p):
    keyword = validate_keyword(p.get("keyword", ""))
    rails = validate_rails(p.get("rails"))
    plain = _text(p, "plaintext", "plaintext")
    normalized, stage1, cipher = hybrid_cipher.encrypt_with_trace(plain, keyword, rails)
    return {
        "input": normalized, "stage1": stage1, "output": cipher,
        "keyword": keyword, "rails": rails,
        "fenceText": stage1,
        "pattern": rail_fence.rail_pattern(len(stage1), rails),
        "order": rail_fence.rail_order(len(stage1), rails),
        "removed": len(str(p.get("plaintext", ""))) - len(normalized),
        "warning": ("Rails are at least the message length, so the Rail Fence stage leaves the "
                    "text unchanged." if rails >= len(normalized) else None),
    }


def api_decrypt(p):
    keyword = validate_keyword(p.get("keyword", ""))
    rails = validate_rails(p.get("rails"))
    cipher = _text(p, "ciphertext", "ciphertext")
    normalized, stage1, plain = hybrid_cipher.decrypt_with_trace(cipher, keyword, rails)
    return {
        "input": normalized, "stage1": stage1, "output": plain,
        "keyword": keyword, "rails": rails,
        "fenceText": stage1,
        "pattern": rail_fence.rail_pattern(len(stage1), rails),
        "order": rail_fence.rail_order(len(stage1), rails),
        "removed": 0,
        "warning": None,
    }


def api_attack_known(p):
    cipher = _text(p, "ciphertext", "ciphertext")
    known = _text(p, "known", "known plaintext")
    offset = _int(p.get("offset", 0), "Offset", 0)
    lengths = _int_list(p.get("keyLengths", "12"), "Key length", 1, 200, limit=40)
    rmin = _int(p.get("railMin", 2), "Minimum rails", 2, 10_000)
    rmax = _int(p.get("railMax", 20), "Maximum rails", 2, 10_000)
    use_lm = bool(p.get("languageModel", True))
    result = attack.known_plaintext_attack(cipher, known, lengths, (rmin, rmax), offset, use_lm)

    derivation = []
    if result.selected is not None:
        derivation = [
            {"index": i, "plain": pl, "stage1": s1, "slot": slot, "key": key}
            for i, pl, s1, slot, key in attack.derivation_table(
                cipher, known, result.selected.rails, result.selected.key_length, offset, rows=60)
        ]
    original = normalize_text(p.get("original", "") or "")

    # Step-by-step working for the interface: every rail guess the attack tried (for one key
    # length), with the fence undone and the key letters it produced. Short ciphertexts only,
    # so every step stays readable on screen.
    working = None
    if len(cipher) <= WORKING_LIMIT:
        m = result.selected.key_length if result.selected is not None else lengths[0]
        guesses = []
        for row in result.trace:
            if row.key_length != m:
                continue
            g = attack.explain_guess(cipher, known, row.rails, m, offset)
            guesses.append({"rails": g["rails"], "stage1": g["stage1"], "pattern": g["pattern"],
                            "letters": g["letters"], "keyword": g["keyword"],
                            "conflicts": g["conflicts"], "consistent": g["consistent"]})
        working = {"keyLength": m, "offset": offset, "known": known, "ciphertext": cipher,
                   "guesses": guesses}
    return {
        "working": working,
        "status": result.status,
        "message": result.message,
        "selected": None if result.selected is None else {
            "rails": result.selected.rails, "keyLength": result.selected.key_length,
            "keyword": result.selected.keyword, "covered": result.selected.covered,
            "redundancy": result.selected.redundancy,
        },
        "consistent": [{"rails": c.rails, "keyLength": c.key_length, "keyword": c.keyword,
                        "fitness": None if math.isinf(c.fitness) else c.fitness}
                       for c in result.consistent],
        "trace": [{"rails": t.rails, "keyLength": t.key_length, "key": t.derived_key,
                   "conflicts": t.conflicts, "consistent": t.consistent} for t in result.trace],
        "derivation": derivation,
        "plaintext": result.plaintext,
        "verified": result.verified,
        "matchesOriginal": (result.plaintext == original) if (original and result.plaintext) else None,
        "candidatesTested": result.candidates_tested,
        "charOperations": result.char_operations,
        "elapsedMs": result.elapsed_seconds * 1000,
        "ciphertextLength": len(cipher), "knownLength": len(known),
    }


def api_attack_cipher_only(p):
    cipher = _text(p, "ciphertext", "ciphertext")
    m = _int(p.get("keyLength", 12), "Key length", 1, 200)
    rmin = _int(p.get("railMin", 2), "Minimum rails", 2, 10_000)
    rmax = _int(p.get("railMax", 20), "Maximum rails", 2, 10_000)
    result = attack.ciphertext_only_attack(cipher, m, (rmin, rmax))
    original = normalize_text(p.get("original", "") or "")
    return {
        "rails": result.rails, "keyword": result.keyword, "plaintext": result.plaintext,
        "ranking": [{"rails": r, "score": s} for r, s in result.ranking],
        "candidatesTested": result.candidates_tested,
        "charOperations": result.char_operations,
        "elapsedMs": result.elapsed_seconds * 1000,
        "chi2": fa.chi_squared(result.plaintext),
        "matchesOriginal": (result.plaintext == original) if original else None,
        "ciphertextLength": len(cipher),
    }


def api_frequency(p):
    text = _text(p, "text", "text")
    summary = _freq_summary(text)
    best, ranking = fa.break_shift_by_frequency(text)
    summary["shiftGuess"] = best
    summary["shiftRanking"] = [{"shift": s, "score": sc} for s, sc in ranking[:5]]
    summary["shiftDecryption"] = shift_cipher.decrypt(text, best)[:200]
    return summary


def api_compare(p):
    n = _int(p.get("length", 1000), "Message length", 50, 20_000)
    shift = _int(p.get("shift", 11), "Shift key", 0, 25)
    keyword = validate_keyword(p.get("keyword", sample_data.DEFAULT_KEYWORD))
    rails = validate_rails(p.get("rails", sample_data.DEFAULT_RAILS))
    rng = sample_data.make_rng(5)
    plain = sample_data.generate_english_text(n, rng)
    shift_ct = shift_cipher.encrypt(plain, shift)
    hcc_ct = hybrid_cipher.encrypt(plain, keyword, rails)
    rows = []
    for name, text in (("English plaintext", plain), (f"Shift cipher (k={shift})", shift_ct),
                       ("HCC ciphertext", hcc_ct)):
        s = _freq_summary(text)
        guess, _ = fa.break_shift_by_frequency(text)
        s.update({"name": name, "shiftGuess": guess,
                  "frequencyAttackRecovers": shift_cipher.decrypt(text, guess) == plain})
        rows.append(s)
    trials = 20
    timing = {
        "hccEncrypt": performance.time_calls(lambda: hybrid_cipher.encrypt(plain, keyword, rails), trials)[0] * 1000,
        "hccDecrypt": performance.time_calls(lambda: hybrid_cipher.decrypt(hcc_ct, keyword, rails), trials)[0] * 1000,
        "shiftEncrypt": performance.time_calls(lambda: shift_cipher.encrypt(plain, shift), trials)[0] * 1000,
        "shiftDecrypt": performance.time_calls(lambda: shift_cipher.decrypt(shift_ct, shift), trials)[0] * 1000,
    }
    return {"length": n, "rows": rows, "timing": timing, "trials": trials,
            "keyspaceBits": len(keyword) * math.log2(26)}


def api_benchmark(p):
    lengths = _int_list(p.get("lengths", "50,100,500,1000,5000,10000"), "Lengths", 10, 50_000)
    trials = _int(p.get("trials", 15), "Trials", 1, 100)
    rows = performance.benchmark_ciphers(lengths, trials=trials, attack_trials=max(1, trials // 3))
    return {"rows": rows, "trials": trials}


def api_success(p):
    lengths = _int_list(p.get("lengths", "100,500"), "Ciphertext lengths", 20, 5_000, limit=6)
    sizes = _int_list(p.get("sizes", "8,12,13,14,16,24"), "Known sizes", 1, 200, limit=10)
    trials = _int(p.get("trials", 40), "Trials", 1, 200)
    rows = performance.attack_success_experiment(lengths, sizes, trials=trials)
    return {"rows": rows, "keyLength": performance.KEY_LENGTH, "railRange": performance.RAIL_RANGE}


def api_coa_experiment(p):
    lengths = _int_list(p.get("lengths", "100,250,500,1000"), "Ciphertext lengths", 20, 5_000, limit=6)
    trials = _int(p.get("trials", 10), "Trials", 1, 60)
    return {"rows": performance.ciphertext_only_experiment(tuple(lengths), trials=trials)}


_FULL_RUN_LOCK = threading.Lock()


def api_full_run(_):
    """Run the complete experiment set (about a minute) and overwrite results/*.csv and *.png."""
    if not _FULL_RUN_LOCK.acquire(blocking=False):
        raise ValidationError("A full experiment run is already in progress.")
    try:
        started = performance.time.perf_counter()
        performance.run_all(quick=False, output=lambda *_: None)
        seconds = performance.time.perf_counter() - started
    finally:
        _FULL_RUN_LOCK.release()
    saved = api_saved_results(None)
    saved["seconds"] = seconds
    return saved


def api_saved_results(_):
    """Full-size results saved by the last full experiment run (results/*.csv)."""
    out = {}
    for key, name in (("timing", "timing.csv"), ("attack", "attack_success.csv"),
                      ("cipherOnly", "ciphertext_only.csv")):
        path = os.path.join(performance.RESULTS_DIR, name)
        if not os.path.exists(path):
            out[key] = None
            continue
        with open(path, newline="") as handle:
            rows = []
            for row in csv.DictReader(handle):
                rows.append({k: (float(v) if any(c in v for c in ".e") else int(v))
                             for k, v in row.items()})
            out[key] = rows
    return out


ROUTES = {
    ("GET", "/api/defaults"): api_defaults,
    ("GET", "/api/results"): api_saved_results,
    ("POST", "/api/encrypt"): api_encrypt,
    ("POST", "/api/decrypt"): api_decrypt,
    ("POST", "/api/attack/known"): api_attack_known,
    ("POST", "/api/attack/ciphertext-only"): api_attack_cipher_only,
    ("POST", "/api/frequency"): api_frequency,
    ("POST", "/api/compare"): api_compare,
    ("POST", "/api/experiments/timing"): api_benchmark,
    ("POST", "/api/experiments/attack"): api_success,
    ("POST", "/api/experiments/ciphertext-only"): api_coa_experiment,
    ("POST", "/api/experiments/full"): api_full_run,
}


# --------------------------------------------------------------------- server

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def end_headers(self):
        # the browser must always load the current ui/ files after an edit
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):          # keep the terminal quiet
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  %s\n" % (args[0],))

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, method):
        path = self.path.split("?", 1)[0]
        handler = ROUTES.get((method, path))
        if handler is None:
            if method == "GET" and not path.startswith("/api/"):
                return super().do_GET()
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown endpoint {path}"})
        payload = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length > 5_000_000:
                return self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                       {"error": "Request is too large."})
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body is not valid JSON."})
        try:
            return self._send_json(HTTPStatus.OK, handler(payload))
        except ValidationError as exc:
            return self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
        except Exception as exc:                 # pragma: no cover - shown in the UI
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR,
                                   {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


def main():
    parser = argparse.ArgumentParser(description="HCC Workbench (web interface)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError:
        print(f"Port {args.port} is busy. Try:  python app.py --port {args.port + 1}")
        sys.exit(1)
    url = f"http://{args.host}:{args.port}/"
    print("HCC Workbench is running at", url)
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
