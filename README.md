# HCC - Hybrid Classical Cipher

**Design and Break a Custom Cipher Based on Classical Techniques**
CT-486 Network and Information Security - Complex Computing Problem (CLO3)

Educational two-stage classical cipher (Vigenere + Rail Fence) in Python, with a browser interface that shows every step, a known-plaintext attack, frequency analysis and benchmarks.

HCC encrypts in two stages:

```
Plaintext -> Vigenere (keyword >= 10 letters) -> Rail Fence (>= 2 rails) -> Ciphertext
Ciphertext -> Rail Fence^-1 -> Vigenere^-1 -> Plaintext
```

> **Educational only.** HCC is deliberately breakable (that is the assignment). Never use it to protect real data.

## Group members

| Name | Roll No. |
|---|---|
| Syeda Aiman Munawar | GA-23003 |
| Naverah Farhat | GA-23004 |
| Duaa Khalid | GA-23303 |
| Zubia Junaid | GA-23307 |

Course advisor: Dr. Shariq Mahmood Khan - NED University of Engineering and Technology, Karachi.

## Web interface (HCC Workbench)

```bash
python app.py            # opens http://127.0.0.1:8000 in your browser
python app.py --port 8080
```

This is the only way to run the project. No extra packages are needed: the interface is served by
Python's built-in `http.server`, and every result in the browser is computed by the same modules the
tests use (`app.py` exposes them as a small JSON API; `ui/` holds the HTML, CSS and JavaScript).

| Section | What it shows |
|---|---|
| Encrypt and decrypt | **Animated working of both ciphers**, started automatically after every Encrypt/Decrypt and shown stage by stage in order: the Vigenere table lights up the key row and plaintext column for every letter (with the `(x + k) mod 26` sum beside it), then the letters are written on the rail fence zig-zag and read off rail by rail. Decryption is animated in reverse (mark the zig-zag, fill it rail by rail, read the zig-zag, subtract the key). Finished stages stay on screen. Below it: normalised input, key alignment, rail diagram and output. Live keyword validation. |
| Attack lab | Known-plaintext attack with recovered rails and keyword, contradictions per rail guess chart, full search log, key derivation table `K = (V' - P) mod 26`, verification by re-encryption. Ciphertext-only attack with chi-squared score per rail guess. |
| Frequency analysis | Letter histogram against English, index of coincidence, chi-squared, best single shift; side-by-side English vs Shift vs HCC with the same frequency attack and timing. |
| Performance | "Run full experiments and save" button (rewrites `results/*.csv` and graphs), saved results (timing, attack success vs ciphertext length and known-plaintext size, ciphertext-only success) as charts and tables, smaller live re-runs; time-complexity table. |
| Design and security | How the stages are combined, security analysis and low-cost improvements. |

## Features

| Area | What you get |
|---|---|
| Cipher | Vigenere + Rail Fence, validated keys, any message length, A-Z normalization |
| Attack | Known-plaintext attack that **recovers** rails and keyword from (ciphertext, known segment, assumed key length, rail range); never receives the secret keys |
| Bonus attack | Ciphertext-only attack (per-column chi-squared + rail search) |
| Analysis | Letter frequencies, chi-squared, index of coincidence, Shift-cipher frequency attack |
| Experiments | Real timings (`time.perf_counter`), attack success rate and effort vs ciphertext length / known-plaintext size, CSV + PNG output |
| Interface | Browser UI only (`python app.py`), with step-by-step working of both ciphers (**Perform next step**) |
| Quality | 59 unit tests (including worked Vigenere examples), standard library only (matplotlib optional for graphs) |

## Project structure

```
HCC-Project/
├── app.py                 # web interface server + JSON API (python app.py)
├── ui/                    # index.html, styles.css, app.js for the web interface
├── utils.py               # alphabet, normalization, key validation
├── vigenere.py            # stage 1
├── rail_fence.py          # stage 2
├── hybrid_cipher.py       # HCC = stage 1 then stage 2 (and reverse)
├── shift_cipher.py        # single-stage baseline
├── attack.py              # known-plaintext attack (+ ciphertext-only bonus)
├── frequency_analysis.py  # frequencies, chi-squared, IC, Shift frequency attack
├── sample_data.py         # reproducible English-like test text and random keys
├── performance.py         # timing + attack-success experiments (run from the UI)
├── requirements.txt
├── tests/                 # unittest suites
└── results/               # CSV + PNG written by the full experiment run
```

## Installation and running

Requires Python 3.8 or newer (developed on 3.11).

```bash
python --version
pip install -r requirements.txt      # only matplotlib, optional
python app.py                        # starts the HCC Workbench in your browser
python -m unittest discover -s tests -v   # developers: run the test suite
```

Full experiments (about a minute) are started from **Performance > Run full experiments and save**.

### VS Code
1. *File -> Open Folder...* and choose `HCC-Project`.
2. Install the Microsoft **Python** extension, then *Ctrl+Shift+P -> Python: Select Interpreter*.
3. Open `app.py` and press the **Run** triangle, or open *Terminal -> New Terminal* and run `python app.py`.
4. For tests: *Testing* sidebar -> configure `unittest`, directory `tests`, pattern `test_*.py`.

## Trying every section

| Section | Try this |
|---|---|
| Encrypt and decrypt | Press **Encrypt** with the demo values (or any message, a keyword of 10+ letters and a rail count) and click **Perform next step** to work through it letter by letter. Switch to **Decrypt** to see the reverse working. Try keyword `SHORT` or `ABCABCABCABC` to see validation. |
| Attack lab | **Load demo scenario > Run attack**: only the right rail count is consistent and the keyword is read off. Shorten the known text below the key length to see the attack report insufficient plaintext. **Ciphertext only > Load 600-letter sample > Run attack**. |
| Frequency analysis | **Use English sample**, then **Use last ciphertext**; press **Compare** for English vs Shift vs HCC. |
| Performance | Re-run any experiment, or **Run full experiments and save**. |
| Design and security | Read-only summary. |

## Input handling

Letters are upper-cased; spaces, digits, punctuation and every non A-Z character are **removed**. Decryption therefore returns the *normalized* plaintext (e.g. `MEETMEATNINE`). Formatting is not preserved on purpose, because word boundaries leak structure to an attacker.

## Demonstrating the attack (60-second script for the viva)

1. `python app.py`, **Encrypt and decrypt**, press **Encrypt** with the demo values, note the ciphertext.
2. **Attack this ciphertext** (button under the result) > **Run attack**: the search log shows every rail count; only `rails=4` is consistent; the derivation table shows `K = (V' - P) mod 26` spelling `SECURITYKEYS`.
3. Shorten the known plaintext to 8 letters and run again: the attack honestly reports *not enough known plaintext*.

## Get the code

Repository: https://github.com/zubiajunaid954-bot/HCC-Hybrid-Classical-Cipher

```bash
git clone https://github.com/zubiajunaid954-bot/HCC-Hybrid-Classical-Cipher.git
cd HCC-Hybrid-Classical-Cipher
python app.py
```

## License / academic note

Coursework for CT-486 Network and Information Security (Complex Computing Problem).
