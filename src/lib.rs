use pyo3::prelude::*;
use pyo3::types::PyDict;

mod lexer;
mod lexer_state;
mod lexer_thread;
mod line_counter;
mod parser;
mod scanner;
mod token;
mod tree;

use lexer::BasicLexer;
use lexer_state::LexerState;
use lexer_thread::LexerThread;
use line_counter::LineCounter;
use parser::{LALR_Parser, ParseConf, ParseTable, ParserState, Rule};
use scanner::Scanner;
use token::Token;
use tree::{Meta, Tree};

#[pymodule]
fn lark_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Token>()?;
    m.add_class::<LineCounter>()?;
    m.add_class::<LexerState>()?;
    m.add_class::<Scanner>()?;
    m.add_class::<BasicLexer>()?;
    m.add_class::<LexerThread>()?;
    m.add_class::<Rule>()?;
    m.add_class::<ParseTable>()?;
    m.add_class::<ParseConf>()?;
    m.add_class::<ParserState>()?;
    m.add_class::<LALR_Parser>()?;
    m.add_class::<Meta>()?;
    m.add_class::<Tree>()?;

    let plugins = PyDict::new(m.py());
    plugins.set_item("BasicLexer", m.getattr("BasicLexer")?)?;
    plugins.set_item("LexerThread", m.getattr("LexerThread")?)?;
    plugins.set_item("LALR_Parser", m.getattr("LALR_Parser")?)?;
    m.add("plugins", plugins)?;
    m.add("__version__", "0.1.0")?;

    Ok(())
}
