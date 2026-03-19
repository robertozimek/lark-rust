use crate::token::Token;
use pyo3::prelude::*;

#[pyclass]
pub struct Meta {
    empty: bool,
    line: Option<i32>,
    column: Option<i32>,
    start_pos: Option<i32>,
    end_line: Option<i32>,
    end_column: Option<i32>,
    end_pos: Option<i32>,
}

#[pymethods]
impl Meta {
    #[new]
    pub fn new() -> Self {
        Meta {
            empty: true,
            line: None,
            column: None,
            start_pos: None,
            end_line: None,
            end_column: None,
            end_pos: None,
        }
    }

    #[getter]
    pub fn empty(&self) -> bool {
        self.empty
    }
    #[setter]
    pub fn set_empty(&mut self, val: bool) {
        self.empty = val;
    }

    #[getter]
    pub fn line(&self) -> Option<i32> {
        self.line
    }
    #[setter]
    pub fn set_line(&mut self, val: Option<i32>) {
        self.line = val;
    }

    #[getter]
    pub fn column(&self) -> Option<i32> {
        self.column
    }
    #[setter]
    pub fn set_column(&mut self, val: Option<i32>) {
        self.column = val;
    }

    #[getter]
    pub fn start_pos(&self) -> Option<i32> {
        self.start_pos
    }
    #[setter]
    pub fn set_start_pos(&mut self, val: Option<i32>) {
        self.start_pos = val;
    }

    #[getter]
    pub fn end_line(&self) -> Option<i32> {
        self.end_line
    }
    #[setter]
    pub fn set_end_line(&mut self, val: Option<i32>) {
        self.end_line = val;
    }

    #[getter]
    pub fn end_column(&self) -> Option<i32> {
        self.end_column
    }
    #[setter]
    pub fn set_end_column(&mut self, val: Option<i32>) {
        self.end_column = val;
    }

    #[getter]
    pub fn end_pos(&self) -> Option<i32> {
        self.end_pos
    }
    #[setter]
    pub fn set_end_pos(&mut self, val: Option<i32>) {
        self.end_pos = val;
    }

    pub fn __lark_meta__(&self) -> Self {
        self.clone()
    }
}

impl Clone for Meta {
    fn clone(&self) -> Self {
        Meta {
            empty: self.empty,
            line: self.line,
            column: self.column,
            start_pos: self.start_pos,
            end_line: self.end_line,
            end_column: self.end_column,
            end_pos: self.end_pos,
        }
    }
}

#[pyclass]
pub struct Tree {
    data: String,
    children: Vec<PyObject>,
    _meta: Option<Meta>,
}

#[pymethods]
impl Tree {
    #[new]
    pub fn new(data: String, children: Vec<PyObject>) -> Self {
        Tree {
            data,
            children,
            _meta: None,
        }
    }

    #[getter]
    pub fn data(&self) -> String {
        self.data.clone()
    }

    #[getter]
    pub fn meta(&self) -> Meta {
        self._meta.clone().unwrap_or_else(Meta::new)
    }

    pub fn __repr__(&self) -> String {
        format!("Tree({}, {:?})", self.data, self.children)
    }

    pub fn __str__(&self) -> String {
        self.pretty("  ")
    }

    pub fn pretty(&self, indent_str: &str) -> String {
        self._pretty_impl(0, indent_str)
    }

    #[pyo3(name = "_pretty")]
    fn _pretty_impl(&self, level: usize, indent_str: &str) -> String {
        let mut out = String::new();
        let prefix = indent_str.repeat(level);
        out.push_str(&prefix);
        out.push_str(&self.data);
        out.push('\n');

        let py = unsafe { Python::assume_gil_acquired() };
        for child in &self.children {
            if let Ok(token) = child.extract::<Token>(py) {
                out.push_str(&indent_str.repeat(level + 1));
                out.push_str(&token.value);
                out.push('\n');
            }
        }
        out
    }

    pub fn __lark_meta__(&self) -> Meta {
        self.meta()
    }
}
