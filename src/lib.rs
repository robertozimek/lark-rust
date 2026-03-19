use pyo3::prelude::*;

#[pymodule]
fn lark_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
