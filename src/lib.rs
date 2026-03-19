use pyo3::prelude::*;

mod line_counter;
mod token;
use line_counter::LineCounter;
use token::Token;

#[pymodule]
fn lark_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Token>()?;
    m.add_class::<LineCounter>()?;
    Ok(())
}
