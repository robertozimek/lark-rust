use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySet, PyTuple};
use std::collections::HashMap;

/// A pre-compiled rule: stores the expansion size and origin name
/// so we never touch Python Rule objects during parsing.
struct CompiledRule {
    expansion_size: usize,
    origin_name: String,
    /// The Python callback for this rule.
    callback: Py<PyAny>,
}

/// Encode Shift(n) as n + 1 (always positive), Reduce(rule_idx) as -(idx + 1).
const SHIFT_OFFSET: i64 = 1;

/// Pre-compiled parse table for fast lookups.
#[pyclass]
pub struct CompiledParseTable {
    /// (state, token_name) -> encoded action.
    table: HashMap<(i32, String), i64>,
    /// Terminal names per state (for error messages).
    state_terminal_names: HashMap<i32, Vec<String>>,
    /// Pre-compiled rules indexed by rule_index.
    rules: Vec<CompiledRule>,
    /// Token-type callbacks (str keys from callbacks dict).
    token_callbacks: HashMap<String, Py<PyAny>>,
    start_state: i32,
    end_state: i32,
}

#[pymethods]
impl CompiledParseTable {
    /// Build from a Python ParseConf object.
    #[new]
    fn new(parse_conf: &Bound<'_, PyAny>) -> PyResult<Self> {
        let py = parse_conf.py();
        let states: Bound<'_, PyDict> = parse_conf.getattr("states")?.extract()?;
        let start_state: i32 = parse_conf.getattr("start_state")?.extract()?;
        let end_state: i32 = parse_conf.getattr("end_state")?.extract()?;
        let callbacks: Bound<'_, PyDict> = parse_conf.getattr("callbacks")?.extract()?;

        let shift_cls = py.import("lark.parsers.lalr_analysis")?.getattr("Shift")?;

        let mut rules: Vec<CompiledRule> = Vec::new();
        let mut rule_index_map: HashMap<usize, usize> = HashMap::new();
        let mut token_callbacks: HashMap<String, Py<PyAny>> = HashMap::new();

        for (key, value) in callbacks.iter() {
            if let Ok(s) = key.extract::<String>() {
                token_callbacks.insert(s, value.into());
            } else {
                let py_id = key.as_ptr() as usize;
                let expansion = key.getattr("expansion")?;
                let expansion_size: usize = expansion.len()?;
                let origin = key.getattr("origin")?;
                let origin_name: String = origin.getattr("name")?.extract()?;
                let idx = rules.len();
                rules.push(CompiledRule {
                    expansion_size,
                    origin_name,
                    callback: value.into(),
                });
                rule_index_map.insert(py_id, idx);
            }
        }

        let mut table: HashMap<(i32, String), i64> = HashMap::new();
        let mut state_terminal_names: HashMap<i32, Vec<String>> = HashMap::new();

        for (state_key, transitions) in states.iter() {
            let state_id: i32 = state_key.extract()?;
            let trans_dict: Bound<'_, PyDict> = transitions.extract()?;
            let mut terminals = Vec::new();

            for (tok_name_obj, action_tuple) in trans_dict.iter() {
                let tok_name: String = tok_name_obj.extract()?;
                let tuple_obj: Bound<'_, PyTuple> = action_tuple.extract()?;
                let action = tuple_obj.get_item(0)?;
                let arg = tuple_obj.get_item(1)?;

                let encoded = if action.is(&shift_cls) {
                    let next_state: i64 = arg.extract()?;
                    next_state + SHIFT_OFFSET
                } else {
                    let py_id = arg.as_ptr() as usize;
                    match rule_index_map.get(&py_id) {
                        Some(&idx) => -(idx as i64) - 1,
                        None => {
                            let expansion = arg.getattr("expansion")?;
                            let expansion_size: usize = expansion.len()?;
                            let origin = arg.getattr("origin")?;
                            let origin_name: String = origin.getattr("name")?.extract()?;
                            let cb = callbacks.get_item(&arg)?.ok_or_else(|| {
                                pyo3::exceptions::PyRuntimeError::new_err(
                                    "Rule not found in callbacks",
                                )
                            })?;
                            let idx = rules.len();
                            rules.push(CompiledRule {
                                expansion_size,
                                origin_name,
                                callback: cb.into(),
                            });
                            rule_index_map.insert(py_id, idx);
                            -(idx as i64) - 1
                        }
                    }
                };

                let first_char = tok_name.chars().next().unwrap_or('a');
                if first_char.is_uppercase() || tok_name.starts_with('$') {
                    terminals.push(tok_name.clone());
                }

                table.insert((state_id, tok_name), encoded);
            }

            state_terminal_names.insert(state_id, terminals);
        }

        Ok(CompiledParseTable {
            table,
            state_terminal_names,
            rules,
            token_callbacks,
            start_state,
            end_state,
        })
    }

    #[getter]
    fn start_state(&self) -> i32 {
        self.start_state
    }

    #[getter]
    fn end_state(&self) -> i32 {
        self.end_state
    }

    /// The core feed_token loop, entirely in Rust.
    /// Takes state_stack and value_stack as mutable Python lists,
    /// the token, and is_end flag.
    /// Returns None on shift, or the final value on successful end.
    fn feed_token(
        &self,
        state_stack: &Bound<'_, PyList>,
        value_stack: &Bound<'_, PyList>,
        token: &Bound<'_, PyAny>,
        token_type: &str,
        is_end: bool,
        parser_state: &Bound<'_, PyAny>,
        py: Python<'_>,
    ) -> PyResult<Option<Py<PyAny>>> {
        loop {
            let stack_len = state_stack.len();
            let state: i32 = state_stack.get_item(stack_len - 1)?.extract()?;
            let key = (state, token_type.to_string());

            let encoded = match self.table.get(&key) {
                Some(&v) => v,
                None => {
                    let expected = self
                        .state_terminal_names
                        .get(&state)
                        .cloned()
                        .unwrap_or_default();
                    let expected_set = PySet::new(py, &expected)?;

                    let unexpected_token_cls =
                        py.import("lark.exceptions")?.getattr("UnexpectedToken")?;

                    let kwargs = PyDict::new(py);
                    kwargs.set_item("state", parser_state)?;
                    kwargs.set_item("interactive_parser", py.None())?;

                    let err = unexpected_token_cls.call((token, expected_set), Some(&kwargs))?;
                    return Err(PyErr::from_value(err));
                }
            };

            if encoded > 0 {
                // Shift
                let next_state = (encoded - SHIFT_OFFSET) as i32;
                state_stack.append(next_state)?;

                let value = if let Some(cb) = self.token_callbacks.get(token_type) {
                    cb.call1(py, (token,))?
                } else {
                    token.clone().unbind()
                };
                value_stack.append(value.bind(py))?;
                return Ok(None);
            } else {
                // Reduce
                let rule_idx = ((-encoded) - 1) as usize;
                let rule = &self.rules[rule_idx];
                let size = rule.expansion_size;

                let vstack_len = value_stack.len();
                let sstack_len = state_stack.len();

                let children = if size > 0 {
                    let start = vstack_len - size;
                    let slice = value_stack.get_slice(start, vstack_len);
                    // Delete from both stacks
                    state_stack.del_slice(sstack_len - size, sstack_len)?;
                    value_stack.del_slice(start, vstack_len)?;
                    slice
                } else {
                    PyList::empty(py).into()
                };

                let value = rule.callback.call1(py, (&children,))?;

                // Goto lookup
                let new_sstack_len = state_stack.len();
                let goto_state: i32 = state_stack.get_item(new_sstack_len - 1)?.extract()?;
                let goto_key = (goto_state, rule.origin_name.clone());
                let goto_encoded = self.table.get(&goto_key).ok_or_else(|| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "goto lookup failed: state={}, origin={}",
                        goto_state, rule.origin_name
                    ))
                })?;

                let new_state = (*goto_encoded - SHIFT_OFFSET) as i32;
                state_stack.append(new_state)?;
                value_stack.append(value.bind(py))?;

                if is_end && {
                    let top: i32 = state_stack.get_item(state_stack.len() - 1)?.extract()?;
                    top == self.end_state
                } {
                    let final_val = value_stack.get_item(value_stack.len() - 1)?;
                    return Ok(Some(final_val.unbind()));
                }
            }
        }
    }
}
