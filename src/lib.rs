use pyo3::prelude::*;

mod token;
use token::Token;

#[pymodule]
fn lark_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Token>()?;
    Ok(())
}
