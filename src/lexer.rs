use crate::lexer_state::LexerState;
use crate::line_counter::LineCounter;
use crate::scanner::Scanner;
use crate::token::Token;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use std::collections::{HashMap, HashSet};

pub struct TerminalDef {
    pub name: String,
    pub pattern: String,
    pub priority: i32,
}

fn pattern_has_newline(pattern: &str) -> bool {
    let bytes = pattern.as_bytes();
    // Check for literal \n, \r sequences in the regex pattern text
    for i in 0..bytes.len() {
        if bytes[i] == b'\\' && i + 1 < bytes.len() {
            let next = bytes[i + 1];
            if next == b'n' || next == b'r' {
                return true;
            }
        }
        if bytes[i] == b'\n' {
            return true;
        }
    }
    false
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

#[pyclass]
pub struct BasicLexer {
    terminals: Vec<TerminalDef>,
    ignore_types: HashSet<String>,
    newline_types: HashSet<String>,
    user_callbacks: HashMap<String, Py<PyAny>>,
    callback: HashMap<String, Py<PyAny>>,
    scanner: Option<Scanner>,
    re_module: Py<PyAny>,
    g_regex_flags: i32,
    use_bytes: bool,
    terminals_by_name: Py<PyAny>,
}

#[pymethods]
impl BasicLexer {
    #[new]
    pub fn new(conf: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Self> {
        let terminals = extract_terminals(conf, py)?;
        let ignore_types = extract_ignore(conf)?;
        let re_module: Py<PyAny> = conf.getattr("re_module")?.into();
        let g_regex_flags: i32 = conf.getattr("g_regex_flags")?.extract()?;
        let use_bytes: bool = conf.getattr("use_bytes")?.extract()?;
        let terminals_by_name: Py<PyAny> = conf.getattr("terminals_by_name")?.into();

        let skip_validation: bool = conf
            .getattr("skip_validation")
            .and_then(|v| v.extract())
            .unwrap_or(false);

        if !skip_validation {
            for t in &terminals {
                let compile_result =
                    re_module.call_method1(py, "compile", (&t.pattern, g_regex_flags));
                if compile_result.is_err() {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Cannot compile token {}: {}",
                        t.name, t.pattern
                    )));
                }
            }
            let terminal_names: HashSet<&str> = terminals.iter().map(|t| t.name.as_str()).collect();
            for ign in &ignore_types {
                if !terminal_names.contains(ign.as_str()) {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Ignore terminals are not defined: {}",
                        ign
                    )));
                }
            }
        }

        let mut terminals_sorted = terminals;
        terminals_sorted.sort_by(|a, b| {
            let a_len = a.pattern.len() as i32;
            let b_len = b.pattern.len() as i32;
            (-a.priority, -b_len, &a.name).cmp(&(-b.priority, -a_len, &b.name))
        });

        let newline_types: HashSet<String> = terminals_sorted
            .iter()
            .filter(|t| pattern_has_newline(&t.pattern))
            .map(|t| t.name.clone())
            .collect();

        let user_callbacks = extract_callbacks(conf)?;

        Ok(BasicLexer {
            terminals: terminals_sorted,
            ignore_types,
            newline_types,
            user_callbacks,
            callback: HashMap::new(),
            scanner: None,
            re_module,
            g_regex_flags,
            use_bytes,
            terminals_by_name,
        })
    }

    pub fn make_lexer_state(&self, text: &str) -> LexerState {
        let line_ctr = LineCounter::new("\n".to_string());
        LexerState::new(text.to_string(), line_ctr, None)
    }

    /// Build the scanner, integrating _create_unless from lark.
    fn _build_scanner(&mut self, py: Python<'_>) -> PyResult<()> {
        let lark_lexer = py.import("lark.lexer")?;
        let create_unless_fn = lark_lexer.getattr("_create_unless")?;
        let call_chain_cls = lark_lexer.getattr("CallChain")?;
        let pattern_re_cls = lark_lexer.getattr("PatternRE")?;
        let terminal_def_cls = lark_lexer.getattr("TerminalDef")?;

        let py_terminals = pyo3::types::PyList::empty(py);
        for t in &self.terminals {
            let pattern_obj = pattern_re_cls.call1((&t.pattern,))?;
            let td = terminal_def_cls.call1((&t.name, pattern_obj, t.priority))?;
            py_terminals.append(td)?;
        }

        let result = create_unless_fn.call1((
            py_terminals,
            self.g_regex_flags,
            self.re_module.bind(py),
            self.use_bytes,
        ))?;

        let new_terminals: Vec<Bound<'_, PyAny>> = result.get_item(0)?.extract()?;
        let callback_dict: Bound<'_, PyDict> = result.get_item(1)?.extract()?;

        let mut callback: HashMap<String, Py<PyAny>> = HashMap::new();
        for (key, value) in callback_dict.iter() {
            let key_str: String = key.extract()?;
            callback.insert(key_str, value.into());
        }

        // Merge user callbacks using CallChain where both exist.
        // Build condition lambda via PyCFunction closure (no eval()).
        for (type_name, user_cb) in &self.user_callbacks {
            if let Some(existing_cb) = callback.get(type_name) {
                let type_name_owned = type_name.clone();
                let cond = pyo3::types::PyCFunction::new_closure(
                    py,
                    None,
                    None,
                    move |args: &Bound<'_, PyTuple>,
                          _kwargs: Option<&Bound<'_, PyDict>>|
                          -> PyResult<bool> {
                        let t = args.get_item(0)?;
                        let token_type: String = t.getattr("type")?.extract()?;
                        Ok(token_type == type_name_owned)
                    },
                )?;
                let chain = call_chain_cls.call1((existing_cb.bind(py), user_cb.bind(py), cond))?;
                callback.insert(type_name.clone(), chain.into());
            } else {
                callback.insert(type_name.clone(), user_cb.clone_ref(py));
            }
        }

        let scanner_terminals: Vec<(String, String)> = new_terminals
            .iter()
            .map(|t| {
                let name: String = t.getattr("name").unwrap().extract().unwrap();
                let pattern = t.getattr("pattern").unwrap();
                let regexp: String = pattern
                    .call_method0("to_regexp")
                    .unwrap()
                    .extract()
                    .unwrap();
                (name, regexp)
            })
            .collect();

        self.scanner = Some(Scanner::new(scanner_terminals)?);
        self.callback = callback;
        Ok(())
    }

    /// Main token loop. Uses iteration (not recursion) for ignored tokens.
    pub fn next_token(
        &mut self,
        lexer_state: &mut LexerState,
        parser_state: &Bound<'_, PyAny>,
        py: Python<'_>,
    ) -> PyResult<Token> {
        if self.scanner.is_none() {
            self._build_scanner(py)?;
        }
        let scanner = self.scanner.as_ref().unwrap();
        let text = &lexer_state.text;

        loop {
            let pos = lexer_state.line_ctr.char_pos as usize;

            if pos >= text.len() {
                return Err(pyo3::exceptions::PyEOFError::new_err("EOF"));
            }

            let (matched, type_) = match scanner.match_(text, pos) {
                Some(m) => m,
                None => return self._raise_unexpected(lexer_state, parser_state, pos, py),
            };

            let has_newline = self.newline_types.contains(&type_);

            if self.ignore_types.contains(&type_) {
                // Invoke callback for ignored tokens (e.g. COMMENT)
                if let Some(cb) = self.callback.get(&type_) {
                    let t = Token::new(
                        type_,
                        matched.to_string(),
                        pos as i32,
                        lexer_state.line_ctr.line,
                        lexer_state.line_ctr.column,
                        None,
                        None,
                        None,
                    );
                    cb.call1(py, (t,))?;
                }
                lexer_state.line_ctr.feed(matched, has_newline);
                continue; // Loop instead of recursive call
            }

            let start_line = lexer_state.line_ctr.line;
            let start_column = lexer_state.line_ctr.column;

            lexer_state.line_ctr.feed(matched, has_newline);

            let mut token = Token::new(
                type_.clone(),
                matched.to_string(),
                pos as i32,
                start_line,
                start_column,
                Some(lexer_state.line_ctr.line),
                Some(lexer_state.line_ctr.column),
                Some(lexer_state.line_ctr.char_pos),
            );

            if let Some(callback) = self.callback.get(&type_) {
                let result = callback.call1(py, (token.clone(),))?;
                if let Ok(t) = result.extract::<Token>(py) {
                    token = t;
                } else {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Callbacks must return a token (returned {:?})",
                        result
                    )));
                }
            }

            // Move token into last_token, return a clone.
            // This is one clone instead of the previous two.
            let ret = token.clone();
            lexer_state.last_token = Some(token);
            return Ok(ret);
        }
    }
}

impl BasicLexer {
    /// Raise UnexpectedCharacters — cold path, kept out of the hot loop.
    #[cold]
    fn _raise_unexpected(
        &self,
        lexer_state: &LexerState,
        parser_state: &Bound<'_, PyAny>,
        pos: usize,
        py: Python<'_>,
    ) -> PyResult<Token> {
        let lark_exc = py.import("lark.exceptions")?;
        let unexpected_chars = lark_exc.getattr("UnexpectedCharacters")?;

        let allowed: Vec<&String> = self
            .scanner
            .as_ref()
            .unwrap()
            .allowed_types()
            .iter()
            .filter(|t| !self.ignore_types.contains(*t))
            .collect();
        let allowed_py = pyo3::types::PySet::new(py, &allowed)?;

        let last_token_list = if let Some(ref lt) = lexer_state.last_token {
            pyo3::types::PyList::new(py, &[lt.clone().into_pyobject(py)?])?
        } else {
            pyo3::types::PyList::empty(py)
        };

        let kwargs = PyDict::new(py);
        kwargs.set_item("allowed", allowed_py)?;
        kwargs.set_item("token_history", last_token_list)?;
        kwargs.set_item("state", parser_state)?;
        kwargs.set_item("terminals_by_name", self.terminals_by_name.bind(py))?;

        let err = unexpected_chars.call(
            (
                &lexer_state.text,
                pos as i32,
                lexer_state.line_ctr.line,
                lexer_state.line_ctr.column,
            ),
            Some(&kwargs),
        )?;

        Err(PyErr::from_value(err))
    }
}
