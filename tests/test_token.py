import lark_rust

def test_token_creation():
    token = lark_rust.Token("WORD", "hello", 0, 1, 1)
    assert token.type == "WORD"
    assert token.value == "hello"
    assert token.line == 1
    assert token.column == 1

def test_token_str():
    token = lark_rust.Token("WORD", "hello", 0, 1, 1)
    assert str(token) == "hello"