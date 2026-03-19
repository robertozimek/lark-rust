use crate::lexer::BasicLexer;
use crate::token::Token;
use crate::tree::Tree;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

#[pyclass]
pub struct Rule {
    origin: String,
    expansion: Vec<String>,
}

#[pymethods]
impl Rule {
    #[new]
    pub fn new(origin: String, expansion: Vec<String>) -> Self {
        Rule { origin, expansion }
    }

    #[getter]
    pub fn origin(&self) -> String {
        self.origin.clone()
    }

    #[getter]
    pub fn expansion(&self) -> Vec<String> {
        self.expansion.clone()
    }
}

impl Clone for Rule {
    fn clone(&self) -> Self {
        Rule {
            origin: self.origin.clone(),
            expansion: self.expansion.clone(),
        }
    }
}

#[pyclass]
pub struct ParseTable {
    start_states: HashMap<String, i32>,
    end_states: HashMap<String, i32>,
    states: HashMap<i32, HashMap<String, (String, i32)>>,
    rules: Vec<Rule>,
}

#[pymethods]
impl ParseTable {
    #[new]
    pub fn new(
        start_states: HashMap<String, i32>,
        end_states: HashMap<String, i32>,
        states: HashMap<i32, HashMap<String, (String, i32)>>,
        rules: Vec<(String, Vec<String>)>,
    ) -> Self {
        let rules = rules
            .into_iter()
            .map(|(origin, expansion)| Rule::new(origin, expansion))
            .collect();
        ParseTable {
            start_states,
            end_states,
            states,
            rules,
        }
    }

    #[getter]
    pub fn start_states(&self) -> HashMap<String, i32> {
        self.start_states.clone()
    }

    #[getter]
    pub fn end_states(&self) -> HashMap<String, i32> {
        self.end_states.clone()
    }

    #[getter]
    pub fn states(&self) -> HashMap<i32, HashMap<String, (String, i32)>> {
        self.states.clone()
    }

    #[getter]
    pub fn rules(&self) -> Vec<Rule> {
        self.rules.clone()
    }
}

impl Clone for ParseTable {
    fn clone(&self) -> Self {
        ParseTable {
            start_states: self.start_states.clone(),
            end_states: self.end_states.clone(),
            states: self.states.clone(),
            rules: self.rules.clone(),
        }
    }
}

#[pyclass]
pub struct ParseConf {
    parse_table: ParseTable,
    callbacks: Py<PyDict>,
    start: String,
    start_state: i32,
    end_state: i32,
}

#[pymethods]
impl ParseConf {
    #[new]
    pub fn new(parse_table: ParseTable, callbacks: Py<PyDict>, start: String) -> Self {
        let start_state = *parse_table.start_states.get(&start).unwrap_or(&0);
        let end_state = *parse_table.end_states.get(&start).unwrap_or(&0);
        ParseConf {
            parse_table,
            callbacks,
            start,
            start_state,
            end_state,
        }
    }

    #[getter]
    pub fn parse_table(&self) -> ParseTable {
        self.parse_table.clone()
    }

    #[getter]
    pub fn start(&self) -> String {
        self.start.clone()
    }

    #[getter]
    pub fn start_state(&self) -> i32 {
        self.start_state
    }

    #[getter]
    pub fn end_state(&self) -> i32 {
        self.end_state
    }
}

impl Clone for ParseConf {
    fn clone(&self) -> Self {
        ParseConf {
            parse_table: self.parse_table.clone(),
            callbacks: self
                .callbacks
                .clone_ref(unsafe { Python::assume_gil_acquired() }),
            start: self.start.clone(),
            start_state: self.start_state,
            end_state: self.end_state,
        }
    }
}

#[pyclass]
pub struct ParserState {
    parse_table: ParseTable,
    callbacks: Py<PyDict>,
    start_state: i32,
    end_state: i32,
    lexer: Py<BasicLexer>,
    state_stack: Vec<i32>,
    value_stack: Vec<PyObject>,
}

#[pymethods]
impl ParserState {
    #[new]
    pub fn new(parse_conf: &ParseConf, lexer: Py<BasicLexer>) -> PyResult<Self> {
        let start_state = parse_conf.start_state;
        let state_stack = vec![start_state];
        Ok(ParserState {
            parse_table: parse_conf.parse_table.clone(),
            callbacks: parse_conf
                .callbacks
                .clone_ref(unsafe { Python::assume_gil_acquired() }),
            start_state,
            end_state: parse_conf.end_state,
            lexer,
            state_stack,
            value_stack: Vec::new(),
        })
    }

    #[getter]
    pub fn state_stack(&self) -> Vec<i32> {
        self.state_stack.clone()
    }

    #[getter]
    pub fn lexer(&self) -> Py<BasicLexer> {
        self.lexer
            .clone_ref(unsafe { Python::assume_gil_acquired() })
    }

    pub fn feed_token(&mut self, token: Token, is_end: bool, py: Python<'_>) -> PyResult<PyObject> {
        let states = &self.parse_table.states;
        let end_state = self.end_state;

        loop {
            let current_state = *self.state_stack.last().unwrap();

            let (action_str, arg) = states
                .get(&current_state)
                .and_then(|state_actions| state_actions.get(&token.type_))
                .ok_or_else(|| {
                    pyo3::exceptions::PyValueError::new_err(format!(
                        "Unexpected token {:?}",
                        token.type_
                    ))
                })?;

            if action_str == "shift" {
                self.state_stack.push(*arg);
                let token_py: PyObject = Py::new(py, token)?.into();
                self.value_stack.push(token_py);

                if is_end {
                    return Ok(self.value_stack.last().unwrap().clone_ref(py));
                }
                return Ok(py.None());
            } else {
                let rule_idx = *arg as usize;
                let rule = &self.parse_table.rules[rule_idx];
                let rule_len = rule.expansion.len();

                let symbols: Vec<PyObject> = if rule_len > 0 {
                    let start = self.value_stack.len() - rule_len;
                    let popped: Vec<PyObject> = self.value_stack.drain(start..).collect();
                    self.state_stack.truncate(self.state_stack.len() - rule_len);
                    popped
                } else {
                    Vec::new()
                };

                let tree = Tree::new(rule.origin.clone(), symbols);
                let result: PyObject = Py::new(py, tree)?.into_any().into_pyobject(py)?.into();

                let goto_state = *self.state_stack.last().unwrap();
                let new_state = states
                    .get(&goto_state)
                    .and_then(|actions| actions.get(&rule.origin))
                    .map(|(_, s)| *s)
                    .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("No goto state"))?;

                self.state_stack.push(new_state);
                self.value_stack.push(result);

                if is_end && self.state_stack.last() == Some(&end_state) {
                    return Ok(self.value_stack.last().unwrap().clone_ref(py));
                }
            }
        }
    }
}

#[pyclass]
pub struct LALR_Parser {
    parse_table: ParseTable,
    callbacks: Py<PyDict>,
    start_state: i32,
    end_state: i32,
}

#[pymethods]
impl LALR_Parser {
    #[new]
    pub fn new(parse_conf: &ParseConf, debug: bool, strict: bool) -> Self {
        let _ = (debug, strict);
        LALR_Parser {
            parse_table: parse_conf.parse_table.clone(),
            callbacks: parse_conf
                .callbacks
                .clone_ref(unsafe { Python::assume_gil_acquired() }),
            start_state: parse_conf.start_state,
            end_state: parse_conf.end_state,
        }
    }

    pub fn parse(
        &self,
        lexer: Py<BasicLexer>,
        text: &str,
        parser_state: Py<PyAny>,
        py: Python<'_>,
    ) -> PyResult<PyObject> {
        let state = Py::new(
            py,
            ParserState {
                parse_table: self.parse_table.clone(),
                callbacks: self.callbacks.clone_ref(py),
                start_state: self.start_state,
                end_state: self.end_state,
                lexer: lexer.clone_ref(py),
                state_stack: vec![self.start_state],
                value_stack: Vec::new(),
            },
        )?;
        let mut lexer_thread = lexer.borrow(py).make_lexer_state(text);
        let ps = parser_state.clone_ref(py);

        loop {
            match lexer
                .borrow_mut(py)
                .next_token(&mut lexer_thread, ps.clone_ref(py), py)
            {
                Ok(token) => {
                    state.borrow_mut(py).feed_token(token, false, py)?;
                }
                Err(e) if e.is_instance_of::<pyo3::exceptions::PyEOFError>(py) => {
                    let end_token = Token::new("$END".to_string(), "".to_string(), 0, 0, 0);
                    return state.borrow_mut(py).feed_token(end_token, true, py);
                }
                Err(e) => return Err(e),
            }
        }
    }
}
