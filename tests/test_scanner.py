from lark_rust import Scanner

def test_scanner_basic():
    terminals = [("WORD", "[a-zA-Z]+"), ("NUM", "[0-9]+")]
    scanner = Scanner(terminals)
    match = scanner.match("hello123", 0)
    assert match is not None
    value, type_ = match
    assert value == "hello"
    assert type_ == "WORD"

def test_scanner_second_token():
    terminals = [("WORD", "[a-zA-Z]+"), ("NUM", "[0-9]+")]
    scanner = Scanner(terminals)
    match = scanner.match("hello123", 5)
    assert match is not None
    value, type_ = match
    assert value == "123"
    assert type_ == "NUM"

def test_scanner_no_match():
    terminals = [("WORD", "[a-zA-Z]+")]
    scanner = Scanner(terminals)
    match = scanner.match("123", 0)
    assert match is None
