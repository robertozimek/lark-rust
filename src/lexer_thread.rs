use crate::lexer::BasicLexer;
use crate::lexer_state::LexerState;
use crate::token::Token;
use pyo3::prelude::*;

#[pyclass]
pub struct LexerThread {
    lexer: Py<BasicLexer>,
    state: LexerState,
}

#[pymethods]
impl LexerThread {
    #[new]
    pub fn new(lexer: Py<BasicLexer>, text: &str, py: Python<'_>) -> PyResult<Self> {
        let state = lexer.borrow(py).make_lexer_state(text);
        Ok(LexerThread { lexer, state })
    }

    pub fn next_token(&mut self, parser_state: Py<PyAny>, py: Python<'_>) -> PyResult<Token> {
        self.lexer
            .borrow_mut(py)
            .next_token(&mut self.state, parser_state, py)
    }
}
