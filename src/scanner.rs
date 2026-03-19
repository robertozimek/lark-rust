use fancy_regex::Regex;
use pyo3::prelude::*;

#[pyclass]
pub struct Scanner {
    combined_re: Option<Regex>,
    individual_patterns: Vec<(String, Regex)>,
    group_to_terminal: Vec<String>,
}

impl Scanner {
    /// Get the terminal names this scanner can match.
    pub fn allowed_types(&self) -> &[String] {
        &self.group_to_terminal
    }
}

#[pymethods]
impl Scanner {
    #[new]
    pub fn new(terminals: Vec<(String, String)>) -> PyResult<Self> {
        let mut pattern_parts = Vec::with_capacity(terminals.len());
        let mut group_to_terminal = Vec::with_capacity(terminals.len());
        let mut individual_patterns = Vec::with_capacity(terminals.len());

        for (name, pattern) in terminals.iter() {
            if let Ok(re) = Regex::new(pattern) {
                individual_patterns.push((name.clone(), re));
            }
            pattern_parts.push(format!("({})", pattern));
            group_to_terminal.push(name.clone());
        }

        let combined_re = Regex::new(&pattern_parts.join("|")).ok();

        Ok(Scanner {
            combined_re,
            individual_patterns,
            group_to_terminal,
        })
    }

    /// Match text at the given position. Returns (matched_str, terminal_index).
    /// The terminal_index can be used with allowed_types() to get the name.
    #[pyo3(name = "match")]
    pub fn match_<'py>(&self, text: &'py str, pos: usize) -> Option<(&'py str, String)> {
        let slice = &text[pos..];

        // Try combined regex first — single captures() call finds match + which group
        if let Some(ref combined_re) = self.combined_re {
            if let Ok(Some(caps)) = combined_re.captures(slice) {
                // Check that the overall match starts at pos (i.e. offset 0 in slice)
                if let Some(full) = caps.get(0) {
                    if full.start() == 0 {
                        let match_end = full.end();
                        let matched = &text[pos..pos + match_end];
                        // Find which group matched (groups are 1-indexed)
                        for (i, name) in self.group_to_terminal.iter().enumerate() {
                            if caps.get(i + 1).is_some_and(|m| m.start() == 0) {
                                return Some((matched, name.clone()));
                            }
                        }
                    }
                }
            }
        }

        // Fallback: try each pattern individually
        for (name, pattern) in &self.individual_patterns {
            if let Ok(Some(m)) = pattern.find(slice) {
                if m.start() == 0 {
                    return Some((&text[pos..pos + m.end()], name.clone()));
                }
            }
        }

        None
    }
}
