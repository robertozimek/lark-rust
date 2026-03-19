use pyo3::prelude::*;
use regex::Regex;

#[pyclass]
pub struct Scanner {
    combined_re: Regex,
    group_to_terminal: Vec<String>,
}

#[pymethods]
impl Scanner {
    #[new]
    pub fn new(terminals: Vec<(String, String)>) -> PyResult<Self> {
        let mut pattern_parts = Vec::new();
        let mut group_to_terminal = Vec::new();

        for (name, pattern) in terminals.iter() {
            pattern_parts.push(format!("(?P<{}>{})", name, pattern));
            group_to_terminal.push(name.clone());
        }

        let combined_pattern = pattern_parts.join("|");
        let combined_re = Regex::new(&combined_pattern)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

        Ok(Scanner {
            combined_re,
            group_to_terminal,
        })
    }

    #[pyo3(name = "match")]
    pub fn match_<'py>(&self, text: &'py str, pos: usize) -> Option<(&'py str, String)> {
        if let Some(m) = self.combined_re.find(&text[pos..]) {
            let abs_start = pos + m.start();
            if abs_start != pos {
                return None;
            }

            let full_match = m.as_str();
            let caps = self.combined_re.captures(full_match)?;

            for (i, name) in self.group_to_terminal.iter().enumerate() {
                let group_idx = i + 1;
                if caps.get(group_idx).is_some() {
                    return Some((full_match, name.clone()));
                }
            }
        }
        None
    }
}
