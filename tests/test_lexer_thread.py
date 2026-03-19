from lark_rust import BasicLexer, LexerThread

def test_lexer_thread_basic():
    terminals = [
        ("WORD", r"[a-zA-Z]+", 1),
        ("NUM", r"[0-9]+", 1),
    ]
    lexer = BasicLexer(terminals, [], {})
    thread = LexerThread(lexer, "hello123")
    
    token = thread.next_token(None)
    assert token.value == "hello"
    assert token.type == "WORD"
