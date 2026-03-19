use pyo3::prelude::*;
use pyo3::types::PyTuple;

#[pyclass(module = "lark_rust")]
#[derive(Clone)]
pub struct Token {
    #[pyo3(get, set, name = "type")]
    pub type_: String,
    #[pyo3(get, set)]
    pub value: String,
    #[pyo3(get, set)]
    pub start_pos: i32,
    #[pyo3(get, set)]
    pub line: i32,
    #[pyo3(get, set)]
    pub column: i32,
    #[pyo3(get, set)]
    pub end_line: Option<i32>,
    #[pyo3(get, set)]
    pub end_column: Option<i32>,
    #[pyo3(get, set)]
    pub end_pos: Option<i32>,
}

#[pymethods]
impl Token {
    #[new]
    #[pyo3(signature = (type_, value, start_pos=-1, line=-1, column=-1, end_line=None, end_column=None, end_pos=None))]
    pub fn new(
        type_: String,
        value: String,
        start_pos: i32,
        line: i32,
        column: i32,
        end_line: Option<i32>,
        end_column: Option<i32>,
        end_pos: Option<i32>,
    ) -> Self {
        Token {
            type_,
            value,
            start_pos,
            line,
            column,
            end_line,
            end_column,
            end_pos,
        }
    }

    #[pyo3(signature = (type_=None, value=None))]
    pub fn update(&self, type_: Option<String>, value: Option<String>) -> Self {
        Token {
            type_: type_.unwrap_or_else(|| self.type_.clone()),
            value: value.unwrap_or_else(|| self.value.clone()),
            start_pos: self.start_pos,
            line: self.line,
            column: self.column,
            end_line: self.end_line,
            end_column: self.end_column,
            end_pos: self.end_pos,
        }
    }

    #[classmethod]
    pub fn new_borrow_pos(
        _cls: &Bound<'_, pyo3::types::PyType>,
        type_: String,
        value: String,
        borrow_t: &Token,
    ) -> Self {
        Token {
            type_,
            value,
            start_pos: borrow_t.start_pos,
            line: borrow_t.line,
            column: borrow_t.column,
            end_line: borrow_t.end_line,
            end_column: borrow_t.end_column,
            end_pos: borrow_t.end_pos,
        }
    }

    pub fn __str__(&self) -> &str {
        &self.value
    }

    pub fn __repr__(&self) -> String {
        format!("Token({:?}, {:?})", self.type_, self.value)
    }

    pub fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        // Borrow the value as a Python str without cloning
        let py_str = pyo3::types::PyString::new(py, &self.value);
        py_str.hash()
    }

    pub fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, pyo3::types::PyType>, Bound<'py, PyTuple>)> {
        let cls = py.get_type::<Token>();
        let args = PyTuple::new(
            py,
            &[
                self.type_.clone().into_pyobject(py)?.into_any().unbind(),
                self.value.clone().into_pyobject(py)?.into_any().unbind(),
                self.start_pos.into_pyobject(py)?.into_any().unbind(),
                self.line.into_pyobject(py)?.into_any().unbind(),
                self.column.into_pyobject(py)?.into_any().unbind(),
            ],
        )?;
        Ok((cls, args))
    }

    pub fn __deepcopy__(&self, _memo: &Bound<'_, pyo3::types::PyDict>) -> Self {
        Token {
            type_: self.type_.clone(),
            value: self.value.clone(),
            start_pos: self.start_pos,
            line: self.line,
            column: self.column,
            end_line: None,
            end_column: None,
            end_pos: None,
        }
    }

    /// Returns self — Token is its own lark meta.
    pub fn __lark_meta__(slf: Py<Self>) -> Py<Self> {
        slf
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<PyObject> {
        let py = other.py();
        // Fast path: try extracting as our Token via downcast (avoids full struct copy)
        if let Ok(other_ref) = other.downcast::<Token>() {
            let other_token = other_ref.borrow();
            let eq = self.type_ == other_token.type_ && self.value == other_token.value;
            return Ok(eq.into_pyobject(py)?.to_owned().into_any().unbind());
        }
        // Try str comparison
        if let Ok(other_str) = other.extract::<&str>() {
            let eq = self.value.as_str() == other_str;
            return Ok(eq.into_pyobject(py)?.to_owned().into_any().unbind());
        }
        Ok(py.NotImplemented().into())
    }
}
