from lark import Lark, Tree
import lark_rust


def test_minimal():
    """Test basic parsing with lark_rust plugin"""
    parser = Lark('!start: "a" "b"', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("ab")
    assert isinstance(res, Tree)
    assert res.data == "start"
    assert len(res.children) == 2


def test_token_types():
    """Test that Token types are correct"""
    parser = Lark('''
        start: WORD+
        WORD: /[a-z]+/
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert res.data == "start"
    tokens = res.children
    assert len(tokens) == 2
    assert str(tokens[0]) == "hello"
    assert str(tokens[1]) == "world"


def test_ignored_tokens():
    """Test that ignored tokens (whitespace) work"""
    parser = Lark('''
        start: WORD+
        WORD: /[a-z]+/
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert len(res.children) == 2


def test_nested_rules():
    """Test nested grammar rules"""
    parser = Lark('''
        start: expr+
        expr: term ("+" term)*
        term: FACTOR
        FACTOR: /[0-9]+/
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("1+2+3")
    assert res.data == "start"


def test_filter_in_operator():
    """Test filter with IN operator (comma-separated values)"""
    parser = Lark('''
        start: filter+
        filter: "state" "=" VALUE ("," VALUE)*
        VALUE: "active"|"inactive"
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("state=active,inactive")
    assert res.data == "start"
    assert len(res.children) == 1
    filter_tree = res.children[0]
    assert filter_tree.data == "filter"
    values = [str(c) for c in filter_tree.children]
    assert values == ["active", "inactive"]


def test_filter_with_id():
    """Test filter with numeric ID"""
    parser = Lark('''
        start: filter
        filter: "id" "=" NUM
        NUM: /[0-9]+/
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("id=123")
    assert res.data == "start"
    assert len(res.children) == 1
    filter_tree = res.children[0]
    assert str(filter_tree.children[0]) == "123"


def test_filter_or_operator():
    """Test filter with OR operator"""
    parser = Lark('''
        start: filter ("|" filter)*
        filter: "state" "=" "active"|"inactive"
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("state=active|inactive")
    assert res.data == "start"
    children = res.children
    assert len(children) == 2  # 2 filters (| is filtered)


def test_filter_and_operator():
    """Test filter with AND operator"""
    parser = Lark('''
        start: filter ("&" filter)*
        filter: "id" "=" NUM | "status" "=" VALUE
        NUM: /[0-9]+/
        VALUE: "recommended"
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("id=123&status=recommended")
    assert res.data == "start"
    children = res.children
    assert len(children) == 2  # 2 filters (& is filtered)


def test_filter_complex_combined():
    """Test complex filter with commas: state=active,inactive&id=123&status=recommended"""
    parser = Lark('''
        start: or_expr
        or_expr: and_expr ("|" and_expr)*
        and_expr: atom ("&" atom)*
        atom: "state" "=" STATE_VALUES ("," STATE_VALUES)*
             | "id" "=" NUM
             | "status" "=" STATUS_VALUE
        STATE_VALUES: "active"|"inactive"
        NUM: /[0-9]+/
        STATUS_VALUE: "recommended"
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("state=active,inactive&id=123&status=recommended")
    assert res.data == "start"
    or_expr = res.children[0]
    and_expr = or_expr.children[0]
    assert len(and_expr.children) == 3  # state=active,inactive & id=123 & status=recommended
    first_atom = and_expr.children[0]
    atom_values = [str(c) for c in first_atom.children]
    assert atom_values == ["active", "inactive"]


def test_filter_parentheses_grouping():
    """Test filter with explicit parentheses grouping"""
    parser = Lark('''
        start: or_expr
        or_expr: and_expr ("|" and_expr)*
        and_expr: atom ("&" atom)*
        atom: "(" or_expr ")" | condition
        condition: "state" "=" "active"|"inactive"
                | "id" "=" NUM | "status" "=" VALUE
        NUM: /[0-9]+/
        VALUE: "recommended"
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("(state=active|inactive)&status=recommended")
    assert res.data == "start"
    or_expr = res.children[0]
    and_expr = or_expr.children[0]
    first_atom = and_expr.children[0]
    assert first_atom.data == "atom"
    assert first_atom.children[0].data == "or_expr"


def test_filter_status_values():
    """Test various status values"""
    parser = Lark('''
        start: filter+
        filter: "status" "=" VALUE
        VALUE: "recommended"|"pending"|"rejected"|"approved"
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    for status in ["recommended", "pending", "rejected", "approved"]:
        res = parser.parse(f"status={status}")
        assert res.data == "start"
        filter_tree = res.children[0]
        assert str(filter_tree.children[0]) == status


def test_filter_with_operators():
    """Test filter grammar with various operators (>=, <=, !=, ^~, etc.)"""
    # Using simpler STRING pattern that works with Rust regex (no lookbehind)
    parser = Lark(r'''
        start: or_expr
        or_expr: condition ("|" condition)*
        condition: TOKEN OP values
        OP: ">=" | "<=" | "!=" | "^~" | "$~" | "*~" | "^=" | "$=" | "*=" | "="
        values: value ("," value)*
        value: ESCAPED_STRING | TOKEN
        TOKEN: /[^,"|!=><^$*~\s]+/

        %import common.ESCAPED_STRING
        %import common.WS_INLINE
        %ignore WS_INLINE
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    
    # Test equals operator
    res = parser.parse("state=active")
    assert res.data == "start"
    assert len(res.children) == 1
    or_expr = res.children[0]
    assert or_expr.data == "or_expr"
    cond = or_expr.children[0]
    assert cond.data == "condition"
    # condition children: [TOKEN(key), OP(operator), values]
    assert str(cond.children[0]) == "state"
    assert str(cond.children[1]) == "="
    values_tree = cond.children[2]
    assert values_tree.data == "values"
    # values has children that are "value" trees with TOKEN children
    assert str(values_tree.children[0].children[0]) == "active"
    
    # Test not equals operator
    res = parser.parse("status!=pending")
    assert res.data == "start"
    
    # Test regex operators
    res = parser.parse("name^=john")
    assert res.data == "start"
    
    res = parser.parse("email$=gmail.com")
    assert res.data == "start"
    
    res = parser.parse("tag*~test")
    assert res.data == "start"
    
    # Test comparison operators
    res = parser.parse("count>=10")
    assert res.data == "start"
    
    res = parser.parse("price<=100")
    assert res.data == "start"
    
    # Test multiple values (IN operator)
    res = parser.parse("state=active,inactive")
    assert res.data == "start"
    or_expr = res.children[0]
    cond = or_expr.children[0]
    values_tree = cond.children[2]
    assert values_tree.data == "values"
    assert str(values_tree.children[0].children[0]) == "active"
    assert str(values_tree.children[1].children[0]) == "inactive"
    
    # Test OR operator
    res = parser.parse("status=active|id=123")
    assert res.data == "start"
    or_expr = res.children[0]
    # Should have 3 children: condition | condition (| is filtered)
    assert len(or_expr.children) == 2
    
    # Test string values (ESCAPED_STRING now works with fancy-regex)
    res = parser.parse('name="John Doe"')
    assert res.data == "start"
    or_expr = res.children[0]
    cond = or_expr.children[0]
    values_tree = cond.children[2]
    assert values_tree.data == "values"
    assert str(values_tree.children[0].children[0]) == '"John Doe"'
    
    # Test complex filter
    res = parser.parse('status=active|name^=test|count>=5,10')
    assert res.data == "start"


def test_lark_common_imports():
    """Test various Lark common imports work with Rust lexer"""
    
    # ESCAPED_STRING
    parser = Lark('''
        start: value
        value: ESCAPED_STRING
        %import common.ESCAPED_STRING
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse('"hello world"')
    assert res.data == "start"
    assert str(res.children[0].children[0]) == '"hello world"'
    
    # SIGNED_NUMBER
    parser = Lark('''
        start: value
        value: SIGNED_NUMBER
        %import common.SIGNED_NUMBER
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("-123")
    assert res.data == "start"
    res = parser.parse("+456")
    assert res.data == "start"
    res = parser.parse("789")
    assert res.data == "start"
    
    # NUMBER
    parser = Lark('''
        start: value
        value: NUMBER
        %import common.NUMBER
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("123")
    assert res.data == "start"
    res = parser.parse("123.45")
    assert res.data == "start"
    
    # INT
    parser = Lark('''
        start: value
        value: INT
        %import common.INT
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("123")
    assert res.data == "start"
    
    # FLOAT
    parser = Lark('''
        start: value
        value: FLOAT
        %import common.FLOAT
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("1.5")
    assert res.data == "start"
    
    # WORD
    parser = Lark('''
        start: value
        value: WORD
        %import common.WORD
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello")
    assert res.data == "start"
    res = parser.parse("world")  # WORD only matches letters, not alphanum
    assert res.data == "start"
    
    # DIGIT
    parser = Lark('''
        start: value
        value: DIGIT
        %import common.DIGIT
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("5")
    assert res.data == "start"
    
    # WS (used as ignore, not as a value type)
    parser = Lark('''
        start: WORD+
        %import common.WORD
        %import common.WS
        %ignore WS
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert res.data == "start"
    assert len(res.children) == 2
    
    # WS_INLINE
    parser = Lark('''
        start: value+
        value: WORD
        %import common.WORD
        %import common.WS_INLINE
        %ignore WS_INLINE
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert res.data == "start"
    assert len(res.children) == 2
    
    # SH_COMMENT (needs WS to be ignored too for spaces)
    parser = Lark('''
        start: value+
        value: WORD
        %import common.WORD
        %import common.WS
        %import common.SH_COMMENT
        %ignore WS
        %ignore SH_COMMENT
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert res.data == "start"
    assert len(res.children) == 2
    
    # C_COMMENT (needs WS to be ignored too for spaces)
    parser = Lark('''
        start: value+
        value: WORD
        %import common.WORD
        %import common.WS
        %import common.C_COMMENT
        %ignore WS
        %ignore C_COMMENT
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert res.data == "start"
    assert len(res.children) == 2
    
    # CR and LF are rules (not terminals) - cannot be used directly in grammar
    # Instead test WS which handles newlines properly
