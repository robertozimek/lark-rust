from lark_rust import LineCounter

def test_line_counter_init():
    lc = LineCounter("\n")
    assert lc.char_pos == 0
    assert lc.line == 1
    assert lc.column == 1

def test_line_counter_feed():
    lc = LineCounter("\n")
    lc.feed("hello", False)
    assert lc.char_pos == 5
    assert lc.line == 1
    assert lc.column == 6
    
def test_line_counter_newlines():
    lc = LineCounter("\n")
    lc.feed("hello\n", True)
    assert lc.char_pos == 6
    assert lc.line == 2
    assert lc.column == 1
