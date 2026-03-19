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
| JSON (3 KB nested) | 4.16 ms | 2.45 ms | **1.73 ms** | 2.4x | 1.4x |
| Arithmetic (deep) | 3.08 ms | 2.00 ms | **1.18 ms** | 2.6x | 1.7x |
| Lexer (10k words) | 28.41 ms | 16.89 ms | **10.61 ms** | 2.7x | 1.6x |

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
