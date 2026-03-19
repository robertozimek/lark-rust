use crate::lexer::BasicLexer;
use crate::lexer_state::LexerState;
use crate::token::Token;
use pyo3::prelude::*;
use pyo3::types::PyType;

#[pyclass]
pub struct LexerThread {
    lexer: Py<BasicLexer>,
    #[pyo3(get)]
    pub state: LexerState,
}

#[pymethods]
impl LexerThread {
    #[new]
    pub fn new(lexer: Py<BasicLexer>, lexer_state: LexerState) -> PyResult<Self> {
        Ok(LexerThread {
            lexer,
            state: lexer_state,
        })
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

    pub fn next_token(
        &mut self,
        parser_state: &Bound<'_, pyo3::PyAny>,
        py: Python<'_>,
    ) -> PyResult<Token> {
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

    /// Expose the Token class for lark compatibility (LexerThread._Token)
    #[classattr]
    #[allow(non_snake_case)]
    fn _Token(py: Python<'_>) -> PyResult<Py<PyType>> {
        Ok(py.get_type::<Token>().unbind())
    }
}
