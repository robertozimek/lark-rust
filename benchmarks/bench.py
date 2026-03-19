"""Benchmark: lark-rust vs lark-cython vs pure lark.

Usage:
    python benchmarks/bench.py

Compares parse throughput across three backends (pure lark, lark-cython,
lark-rust) on several workloads.  Backends that aren't installed are
silently skipped.
"""

import json
import statistics
import sys
import time

from lark import Lark

# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

backends = {}

# Pure lark (always available)
backends["lark"] = {}

try:
    import lark_cython
    backends["lark-cython"] = {"_plugins": lark_cython.plugins}
except ImportError:
    pass

try:
    import lark_rust
    backends["lark-rust"] = {"_plugins": lark_rust.plugins}
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Grammars & inputs
# ---------------------------------------------------------------------------

JSON_GRAMMAR = r'''
    ?start: value
    ?value: object | array | string | number | "true" -> true | "false" -> false | "null" -> null
    object: "{" [pair ("," pair)*] "}"
    pair: string ":" value
    array: "[" [value ("," value)*] "]"
    string: ESCAPED_STRING
    number: SIGNED_NUMBER
    %import common.ESCAPED_STRING
    %import common.SIGNED_NUMBER
    %import common.WS
    %ignore WS
'''

EXPR_GRAMMAR = r'''
    ?start: expr
    ?expr: term (("+" | "-") term)*
    ?term: factor (("*" | "/") factor)*
    ?factor: NUMBER | "(" expr ")"
    %import common.NUMBER
    %import common.WS
    %ignore WS
'''

WORDS_GRAMMAR = r'''
    start: WORD+
    WORD: /[a-z]+/
    %ignore " "
'''


def make_json_input(depth=4, breadth=4):
    """Build a nested JSON blob."""
    def _obj(d):
        if d <= 0:
            return 42
        return {f"k{i}": _obj(d - 1) for i in range(breadth)}
    return json.dumps(_obj(depth))


def make_expr_input(depth=8):
    """Build a deeply nested arithmetic expression."""
    if depth <= 0:
        return "1"
    inner = make_expr_input(depth - 1)
    return f"({inner} + {inner})"


def make_words_input(n=10_000):
    """Build a long string of words."""
    words = ["alpha", "bravo", "charlie", "delta", "echo",
             "foxtrot", "golf", "hotel", "india", "juliet"]
    return " ".join(words[i % len(words)] for i in range(n))


WORKLOADS = [
    ("JSON (nested)",     JSON_GRAMMAR,  make_json_input(depth=4, breadth=4)),
    ("Arithmetic (deep)", EXPR_GRAMMAR,  make_expr_input(depth=8)),
    ("Lexer (10k words)", WORDS_GRAMMAR, make_words_input(10_000)),
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

WARMUP = 3
ITERATIONS = 20


def bench_one(parser, text, warmup=WARMUP, iters=ITERATIONS):
    """Return median parse time in seconds."""
    for _ in range(warmup):
        parser.parse(text)
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        parser.parse(text)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return statistics.median(times)


def fmt_ms(seconds):
    if seconds < 0.001:
        return f"{seconds * 1_000_000:8.1f} \u00b5s"
    return f"{seconds * 1_000:8.2f} ms"


def main():
    print(f"Python {sys.version.split()[0]}")
    print(f"Backends: {', '.join(backends)}")
    print(f"Warmup: {WARMUP}  Iterations: {ITERATIONS}")
    print()

    # Pre-build parsers (exclude from timing)
    parsers = {}
    for wl_name, grammar, _ in WORKLOADS:
        for be_name, be_kwargs in backends.items():
            parsers[(wl_name, be_name)] = Lark(
                grammar, parser="lalr", lexer="basic", **be_kwargs
            )

    # Header
    col_w = max(len(name) for name, _, _ in WORKLOADS) + 2
    be_names = list(backends)
    header = f"{'Workload':<{col_w}}"
    for be in be_names:
        header += f" | {be:>14}"
    header += " | vs lark  | vs cython"
    print(header)
    print("-" * len(header))

    for wl_name, grammar, text in WORKLOADS:
        row = f"{wl_name:<{col_w}}"
        times = {}
        for be_name in be_names:
            p = parsers[(wl_name, be_name)]
            t = bench_one(p, text)
            times[be_name] = t
            row += f" | {fmt_ms(t):>14}"

        if "lark-rust" in times and "lark" in times:
            speedup = times["lark"] / times["lark-rust"]
            row += f" | {speedup:5.1f}x  "
        else:
            row += " |         "

        if "lark-rust" in times and "lark-cython" in times:
            speedup = times["lark-cython"] / times["lark-rust"]
            row += f" | {speedup:5.1f}x"
        print(row)

    print()
    print("Input sizes:")
    for wl_name, _, text in WORKLOADS:
        print(f"  {wl_name}: {len(text):,} chars")


if __name__ == "__main__":
    main()
