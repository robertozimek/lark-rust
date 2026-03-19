use crate::lexer_state::LexerState;
use crate::line_counter::LineCounter;
use crate::scanner::Scanner;
use crate::token::Token;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::{HashMap, HashSet};

#[pyclass]
pub struct BasicLexer {
    terminals: Vec<TerminalDef>,
    ignore_types: HashSet<String>,
    newline_types: HashSet<String>,
    callbacks: HashMap<String, Py<PyAny>>,
    scanner: Option<Scanner>,
    terminals_by_name: HashMap<String, usize>,
}

pub struct TerminalDef {
    pub name: String,
    pub pattern: String,
    pub priority: i32,
}

fn pattern_has_newline(pattern: &str) -> bool {
    pattern.contains("\\n") || pattern.contains('\n') || pattern.contains("\\r")
}

fn extract_terminals(conf: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Vec<TerminalDef>> {
    let terminals_list: Vec<Bound<'_, PyAny>> = conf.getattr("terminals")?.extract()?;
    let mut terminals = Vec::with_capacity(terminals_list.len());
    for t in terminals_list {
        let name: String = t.getattr("name")?.extract()?;
        let pattern_obj = t.getattr("pattern")?;
        let to_regexp_fn = pattern_obj.getattr("to_regexp")?;
        let regex_result: Py<PyAny> = to_regexp_fn.call0()?.into();
        let pattern_str: String = regex_result.extract(py)?;
        let priority: i32 = t.getattr("priority")?.extract()?;
        terminals.push(TerminalDef {
            name,
            pattern: pattern_str,
            priority,
        });
    }
    Ok(terminals)
}

fn extract_ignore(conf: &Bound<'_, PyAny>) -> PyResult<HashSet<String>> {
    let ignore_list: Vec<String> = conf.getattr("ignore")?.extract()?;
    Ok(ignore_list.into_iter().collect())
}

fn extract_callbacks(conf: &Bound<'_, PyAny>) -> PyResult<HashMap<String, Py<PyAny>>> {
    let callbacks_obj = conf.getattr("callbacks")?;
    if callbacks_obj.is_none() {
        return Ok(HashMap::new());
    }
    let callbacks_dict: Bound<'_, PyDict> = callbacks_obj.extract()?;
    let mut result = HashMap::new();
    for (key, value) in callbacks_dict.iter() {
        let key_str: String = key.extract()?;
        result.insert(key_str, value.into());
    }
    Ok(result)
}

#[pymethods]
impl BasicLexer {
    #[new]
    pub fn new(conf: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Self> {
        let terminals = extract_terminals(&conf, py)?;
        let ignore_types = extract_ignore(&conf)?;

        let mut terminals_sorted = terminals;
        terminals_sorted.sort_by(|a, b| {
            let a_len = a.pattern.len() as i32;
            let b_len = b.pattern.len() as i32;
            (-a.priority, -b_len, &a.name).cmp(&(-b.priority, -a_len, &b.name))
        });

        let mut terminals_by_name = HashMap::new();
        for (i, t) in terminals_sorted.iter().enumerate() {
            terminals_by_name.insert(t.name.clone(), i);
        }

        let newline_types: HashSet<String> = terminals_sorted
            .iter()
            .filter(|t| pattern_has_newline(&t.pattern))
            .map(|t| t.name.clone())
            .collect();

        let callbacks = extract_callbacks(&conf)?;

        Ok(BasicLexer {
            terminals: terminals_sorted,
            ignore_types,
            newline_types,
            callbacks,
            scanner: None,
            terminals_by_name,
        })
    }

    pub fn make_lexer_state(&self, text: &str) -> LexerState {
        let line_ctr = LineCounter::new("\n".to_string());
        LexerState::new(text.to_string(), line_ctr)
    }

    pub fn next_token(
        &mut self,
        lexer_state: &mut LexerState,
        parser_state: Py<PyAny>,
        py: Python<'_>,
    ) -> PyResult<Token> {
        if self.scanner.is_none() {
            let terminals: Vec<(String, String)> = self
                .terminals
                .iter()
                .map(|t| (t.name.clone(), t.pattern.clone()))
                .collect();
            self.scanner = Some(Scanner::new(terminals).expect("Failed to create scanner"));
        }
        let scanner = self.scanner.as_ref().unwrap();
        let text = &lexer_state.text;
        let pos = lexer_state.line_ctr.char_pos as usize;

        if pos >= text.len() {
            return Err(pyo3::exceptions::PyEOFError::new_err("EOF"));
        }

        if let Some((matched, type_)) = scanner.match_(text, pos) {
            let start_line = lexer_state.line_ctr.line;
            let start_column = lexer_state.line_ctr.column;

            let mut token = Token::new(
                type_.clone(),
                matched.to_string(),
                pos as i32,
                start_line,
                start_column,
            );

            let has_newline = self.newline_types.contains(&type_);
            lexer_state.line_ctr.feed(matched, has_newline);

            token.end_line = Some(lexer_state.line_ctr.line);
            token.end_column = Some(lexer_state.line_ctr.column);
            token.end_pos = Some(lexer_state.line_ctr.char_pos);

            if let Some(callback) = self.callbacks.get(&type_) {
                let result = callback.call1(py, (token.clone(),))?;
                token = result.extract(py)?;
            }

            if self.ignore_types.contains(&type_) {
                return self.next_token(lexer_state, parser_state, py);
            }

            lexer_state.last_token = Some(token.clone());
            return Ok(token);
        }

        Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Unexpected character at position {}",
            pos
        )))
    }
}
