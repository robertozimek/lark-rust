use pyo3::prelude::*;

#[pyclass]
#[derive(Clone)]
pub struct LineCounter {
    #[pyo3(get)]
    pub char_pos: i32,
    #[pyo3(get)]
    pub line: i32,
    #[pyo3(get)]
    pub column: i32,
    #[pyo3(get)]
    pub line_start_pos: i32,
    #[pyo3(get)]
    pub newline_char: String,
    /// Cached first byte of newline_char for fast single-byte comparison
    nl_byte: u8,
}

#[pymethods]
impl LineCounter {
    #[new]
    pub fn new(newline_char: String) -> Self {
        let nl_byte = newline_char.as_bytes().first().copied().unwrap_or(b'\n');
        LineCounter {
            char_pos: 0,
            line: 1,
            column: 1,
            line_start_pos: 0,
            newline_char,
            nl_byte,
        }
    }

    /// Consume a token and update line/column tracking.
    /// Single pass: counts newlines and finds last newline position simultaneously.
    pub fn feed(&mut self, token: &str, test_newline: bool) {
        if test_newline {
            let nl = self.nl_byte;
            let bytes = token.as_bytes();
            let mut newlines: i32 = 0;
            let mut last_nl_pos: i32 = -1;

            for (i, &b) in bytes.iter().enumerate() {
                if b == nl {
                    newlines += 1;
                    last_nl_pos = i as i32;
                }
            }

            if newlines > 0 {
                self.line += newlines;
                self.line_start_pos = self.char_pos + last_nl_pos + 1;
            }
        }
        self.char_pos += token.len() as i32;
        self.column = self.char_pos - self.line_start_pos + 1;
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<PyObject> {
        let py = other.py();
        if let Ok(other_lc) = other.extract::<LineCounter>() {
            let eq =
                self.char_pos == other_lc.char_pos && self.newline_char == other_lc.newline_char;
            return Ok(eq.into_pyobject(py)?.to_owned().into_any().unbind());
        }
        Ok(py.NotImplemented().into())
    }
}
