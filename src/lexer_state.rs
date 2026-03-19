use crate::line_counter::LineCounter;
use crate::token::Token;
use pyo3::prelude::*;

#[pyclass]
#[derive(Clone)]
pub struct LexerState {
    #[pyo3(get)]
    pub text: String,
    #[pyo3(get)]
    pub line_ctr: LineCounter,
    #[pyo3(get, set)]
    pub last_token: Option<Token>,
}

#[pymethods]
impl LexerState {
    #[new]
    #[pyo3(signature = (text, line_ctr, last_token=None))]
    pub fn new(text: String, line_ctr: LineCounter, last_token: Option<Token>) -> Self {
        LexerState {
            text,
            line_ctr,
            last_token,
        }
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<PyObject> {
        let py = other.py();
        if let Ok(other_ls) = other.extract::<LexerState>() {
            // text identity check isn't possible across Rust/Python, use equality
            let eq = self.text == other_ls.text
                && self.line_ctr.char_pos == other_ls.line_ctr.char_pos
                && self.line_ctr.newline_char == other_ls.line_ctr.newline_char;
            return Ok(eq.into_pyobject(py)?.to_owned().into_any().unbind());
        }
        Ok(py.NotImplemented())
    }

    fn __copy__(&self) -> Self {
        self.clone()
    }

    /// Expose the Token class for lark compatibility (LexerState._Token)
    #[classattr]
    #[allow(non_snake_case)]
    fn _Token(py: Python<'_>) -> PyResult<Py<pyo3::types::PyType>> {
        Ok(py.get_type::<Token>().unbind())
    }
}
