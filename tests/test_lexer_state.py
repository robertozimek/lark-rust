from lark_rust import LexerState, LineCounter

def test_lexer_state_init():
    lc = LineCounter("\n")
    state = LexerState("hello world", lc)
    assert state.text == "hello world"
    assert state.last_token is None