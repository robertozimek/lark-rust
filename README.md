# lark-rust

High-performance Rust-accelerated drop-in replacement for [lark](https://github.com/lark-parser/lark)'s LALR parser stack. A faster alternative to [lark-cython](https://github.com/lark-parser/lark_cython).

## Installation

```bash
pip install lark-rust
```

## Usage

```python
from lark import Lark
import lark_rust

parser = Lark(grammar, parser='lalr', _plugins=lark_rust.plugins)
result = parser.parse(text)
```

That's it — same lark API, just faster.

## Benchmarks

Measured on Apple M4 Pro, Python 3.13, median of 20 iterations:

| Workload | lark | lark-cython | lark-rust | vs lark | vs cython |
|---|---|---|---|---|---|
| JSON (3 KB nested) | 4.02 ms | 2.39 ms | **2.04 ms** | 2.0x | 1.2x |
| Arithmetic (deep) | 3.22 ms | 1.98 ms | **1.29 ms** | 2.5x | 1.5x |
| Lexer (10k words) | 28.66 ms | 16.50 ms | **11.44 ms** | 2.5x | 1.4x |

Reproduce with `python benchmarks/bench.py` (install `lark-cython` for the three-way comparison).

## What's accelerated

The Rust native extension accelerates the hot-path components:

- **LALR parser state machine** — `feed_token` loop with pre-compiled parse table (HashMap lookup, no Python dict overhead)
- **Token** — creation, hashing, equality comparison
- **Scanner** — regex matching via `fancy-regex`
- **BasicLexer** — token loop with single-pass newline counting
- **LineCounter** — position tracking
- **LexerState** — lexer state management

The tree builder, tree traversal, and error recovery are implemented in Python with full lark compatibility:

- **ContextualLexer**, **LALR_Parser** (with serialize/deserialize/on_error)
- **ParseTreeBuilder** with ExpandSingleChild, PropagatePositions, ChildFilter
- **Tree** with iter_subtrees, find_data, scan_values, pretty printing

## lark-cython compatibility

lark-rust is a drop-in replacement for lark-cython. All plugins supported by lark-cython are supported:

- `BasicLexer`, `ContextualLexer`, `LexerThread`
- `LALR_Parser`, `_Parser`, `ParseTreeBuilder`

## Requirements

- Python >= 3.8
- lark >= 1.0

## License

MIT
