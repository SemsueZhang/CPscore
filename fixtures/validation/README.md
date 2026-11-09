These are deliberately small, human-authored harness fixtures, not a benchmark
suite and not evidence of general algorithm correctness.

Task: read `n` (1 <= n <= 100), followed by exactly `n` integers in [-10^9, 10^9],
and print their sum followed by a newline. The Python oracle uses arbitrary-size
integers. The C++ solution uses a 64-bit accumulator. The intentionally wrong
solutions print the sum plus one. `validator.py` rejects malformed or out-of-range
input. `generator.py SEED CASE_INDEX` deterministically generates a legal case.

`sample.in` is a legal input with positive and negative values. `sample.out` is
manually checked. The isolated integration tests exercise both languages.
