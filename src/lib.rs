use pyo3::prelude::*;
use pyo3::types::PyDict;

mod lexer;
mod lexer_state;
mod lexer_thread;
mod line_counter;
mod scanner;
mod token;

use lexer::BasicLexer;
use lexer_thread::LexerThread;
use scanner::Scanner;
use token::Token;

#[pymodule]
fn lark_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Token>()?;
    m.add_class::<line_counter::LineCounter>()?;
    m.add_class::<lexer_state::LexerState>()?;
    m.add_class::<Scanner>()?;
    m.add_class::<BasicLexer>()?;
    m.add_class::<LexerThread>()?;

    let plugins = PyDict::new(m.py());
    plugins.set_item("BasicLexer", m.getattr("BasicLexer")?)?;
    plugins.set_item("LexerThread", m.getattr("LexerThread")?)?;
    m.add("plugins", plugins)?;
    m.add("__version__", "0.1.0")?;

    Ok(())
}
