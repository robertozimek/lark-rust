use crate::lexer_state::LexerState;
use crate::line_counter::LineCounter;
use crate::scanner::Scanner;
use crate::token::Token;
use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};

#[pyclass]
pub struct BasicLexer {
    terminals: Vec<TerminalDef>,
    ignore_types: HashSet<String>,
    newline_types: HashSet<String>,
    callbacks: HashMap<String, PyObject>,
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

#[pymethods]
impl BasicLexer {
    #[new]
    pub fn new(
        terminals: Vec<(String, String, i32)>,
        ignore: Vec<String>,
        callbacks: HashMap<String, PyObject>,
    ) -> PyResult<Self> {
        let mut terminals: Vec<TerminalDef> = terminals
            .into_iter()
            .map(|(name, pattern, priority)| TerminalDef {
                name,
                pattern,
                priority,
            })
            .collect();

        terminals.sort_by(|a, b| {
            let a_len = a.pattern.len() as i32;
            let b_len = b.pattern.len() as i32;
            (-a.priority, -b_len, &a.name).cmp(&(-b.priority, -a_len, &b.name))
        });

        let mut terminals_by_name = HashMap::new();
        for (i, t) in terminals.iter().enumerate() {
            terminals_by_name.insert(t.name.clone(), i);
        }

        let ignore_types: HashSet<String> = ignore.into_iter().collect();

        let newline_types: HashSet<String> = terminals
            .iter()
            .filter(|t| pattern_has_newline(&t.pattern))
            .map(|t| t.name.clone())
            .collect();

        Ok(BasicLexer {
            terminals,
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
