use crate::lexer::BasicLexer;
use crate::lexer_state::LexerState;
use crate::token::Token;
use pyo3::prelude::*;
use pyo3::types::PyType;

#[pyclass]
pub struct LexerThread {
    lexer: Py<BasicLexer>,
    state: LexerState,
}

#[pymethods]
impl LexerThread {
    #[new]
    pub fn new(
        lexer: Py<BasicLexer>,
        lexer_state: Option<LexerState>,
        py: Python<'_>,
    ) -> PyResult<Self> {
        let state = lexer_state.unwrap_or_else(|| lexer.borrow(py).make_lexer_state(""));
        Ok(LexerThread { lexer, state })
    }

    #[classmethod]
    pub fn from_text(
        _cls: &Bound<'_, PyType>,
        lexer: Py<BasicLexer>,
        text: &str,
        py: Python<'_>,
    ) -> Self {
        let state = lexer.borrow(py).make_lexer_state(text);
        LexerThread { lexer, state }
    }

    pub fn next_token(&mut self, parser_state: Py<PyAny>, py: Python<'_>) -> PyResult<Token> {
        self.lexer
            .borrow_mut(py)
            .next_token(&mut self.state, parser_state, py)
    }

    pub fn __copy__(&self, py: Python<'_>) -> Self {
        LexerThread {
            lexer: self.lexer.clone_ref(py),
            state: self.state.clone(),
        }
    }
}
