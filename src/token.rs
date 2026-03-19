use pyo3::prelude::*;

#[pyclass]
#[derive(Clone)]
pub struct Token {
    #[pyo3(get, name = "type")]
    pub type_: String,
    #[pyo3(get)]
    pub value: String,
    #[pyo3(get)]
    pub start_pos: i32,
    #[pyo3(get)]
    pub line: i32,
    #[pyo3(get)]
    pub column: i32,
    #[pyo3(get)]
    pub end_line: Option<i32>,
    #[pyo3(get)]
    pub end_column: Option<i32>,
    #[pyo3(get)]
    pub end_pos: Option<i32>,
}

#[pymethods]
impl Token {
    #[new]
    pub fn new(type_: String, value: String, start_pos: i32, line: i32, column: i32) -> Self {
        Token {
            type_,
            value,
            start_pos,
            line,
            column,
            end_line: None,
            end_column: None,
            end_pos: None,
        }
    }

    pub fn __str__(&self) -> String {
        self.value.clone()
    }

    pub fn __repr__(&self) -> String {
        format!("Token({}, {})", self.type_, self.value)
    }
}
