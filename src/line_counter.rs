use pyo3::prelude::*;

#[pyclass]
pub struct LineCounter {
    #[pyo3(get)]
    pub char_pos: i32,
    #[pyo3(get)]
    pub line: i32,
    #[pyo3(get)]
    pub column: i32,
    #[pyo3(get)]
    pub line_start_pos: i32,
    newline_char: String,
}

#[pymethods]
impl LineCounter {
    #[new]
    pub fn new(newline_char: String) -> Self {
        LineCounter {
            char_pos: 0,
            line: 1,
            column: 1,
            line_start_pos: 0,
            newline_char,
        }
    }

    pub fn feed(&mut self, token: &str, test_newline: bool) {
        if test_newline {
            let newlines = token.matches(&self.newline_char).count() as i32;
            if newlines > 0 {
                self.line += newlines;
                if let Some(pos) = token.rfind(&self.newline_char) {
                    self.line_start_pos = self.char_pos + pos as i32 + 1;
                }
            }
        }
        self.char_pos += token.len() as i32;
        self.column = self.char_pos - self.line_start_pos + 1;
    }
}
