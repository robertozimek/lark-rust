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

## What's accelerated

The Rust native extension accelerates the hot-path components:

- **Token** — creation, hashing, equality comparison
- **Scanner** — regex matching via `fancy-regex`
- **BasicLexer** — token loop with single-pass newline counting
- **LineCounter** — position tracking
- **LexerState** — lexer state management

The parser, tree builder, and tree traversal are implemented in Python with full lark compatibility:

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
