use crate::line_counter::LineCounter;
use crate::token::Token;
use pyo3::prelude::*;

#[pyclass]
pub struct LexerState {
    #[pyo3(get)]
    pub text: String,
    #[pyo3(get)]
    pub line_ctr: LineCounter,
    #[pyo3(get)]
    pub last_token: Option<Token>,
}

#[pymethods]
impl LexerState {
    #[new]
    pub fn new(text: String, line_ctr: LineCounter) -> Self {
        LexerState {
            text,
            line_ctr,
            last_token: None,
        }
    }
}
