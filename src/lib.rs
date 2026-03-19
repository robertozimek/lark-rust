use pyo3::prelude::*;

mod lexer_state;
mod line_counter;
mod scanner;
mod token;
use lexer_state::LexerState;
use line_counter::LineCounter;
use scanner::Scanner;
use token::Token;

#[pymodule]
fn lark_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Token>()?;
    m.add_class::<LineCounter>()?;
    m.add_class::<LexerState>()?;
    m.add_class::<Scanner>()?;
    Ok(())
}
