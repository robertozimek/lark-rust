"""Exact reproduction from https://github.com/robertozimek/lark-rust/issues/1"""
from lark import Lark
import lark_rust

GRAMMAR = r"""// ==================== TOKENS ====================
INT_NUMBER: /\d+/
FLOAT_NUMBER: /\d*\.\d+|\d+e(\+|\-)\d+/
VARIABLE: /[a-zA-Z_]\w*/
NEWLINE: "\n"
PLUS: "+"
MINUS: "-"
MUL: "*"
DIV: "/"
MOD: "%"
POWER: "**"
EQ: "="
LPAR: "("
RPAR: ")"
LBRACK: "["
RBRACK: "]"
COMMA: ","
COLON: ":"
TYPE_COMPLEX: "complex"
TYPE_FLOAT: "float"
TYPE_INT: "int"
TYPE_VECTOR: "vector"
SUM_KEYWORD: "sum"
MEAN_KEYWORD: "mean"
DOT_KEYWORD: "dot"
PRINT_KEYWORD: "print"

%ignore /[ \t]+/
%ignore /\/\/.*\n/

start: vec_lang_program

vec_lang_program: vec_lang_instructions_sequence

vec_lang_instructions_sequence: (NEWLINE* vec_lang_instruction)+ NEWLINE*

vec_lang_instruction: arithmetic_expression_level_1
    | function_decl
    | variable_expression EQ arithmetic_expression_level_1
    | PRINT_KEYWORD LPAR function_args RPAR

arithmetic_expression_level_1: arithmetic_expression_level_1 PLUS arithmetic_expression_level_2
    | arithmetic_expression_level_1 MINUS arithmetic_expression_level_2
    | arithmetic_expression_level_2

arithmetic_expression_level_2: arithmetic_expression_level_2 MUL arithmetic_expression_level_3
    | arithmetic_expression_level_2 DIV arithmetic_expression_level_3
    | arithmetic_expression_level_2 MOD arithmetic_expression_level_3
    | arithmetic_expression_level_3

arithmetic_expression_level_3: arithmetic_expression_level_3 POWER arithmetic_expression_level_4
    | arithmetic_expression_level_4

arithmetic_expression_level_4: number_expression
    | variable_expression
    | vector
    | indexing
    | function_call
    | LPAR arithmetic_expression_level_1 RPAR

number_expression: number
    | complex_number

number: INT_NUMBER
    | FLOAT_NUMBER
    | PLUS INT_NUMBER
    | MINUS INT_NUMBER
    | PLUS FLOAT_NUMBER
    | MINUS FLOAT_NUMBER

complex_number: TYPE_COMPLEX LPAR number COMMA number RPAR
    | number VARIABLE

variable_expression: VARIABLE

vector: LBRACK components RBRACK
    | LBRACK range RBRACK
    | slicing

components: arithmetic_expression_level_1
    | components COMMA arithmetic_expression_level_1

range: INT_NUMBER COLON INT_NUMBER
    | MINUS INT_NUMBER COLON INT_NUMBER
    | INT_NUMBER COLON MINUS INT_NUMBER
    | MINUS INT_NUMBER COLON MINUS INT_NUMBER

indexing: variable_expression LBRACK INT_NUMBER RBRACK
    | vector LBRACK INT_NUMBER RBRACK

slicing: variable_expression LBRACK range RBRACK
    | vector LBRACK range RBRACK

function_call: variable_expression LPAR function_args RPAR
    | SUM_KEYWORD LPAR function_args RPAR
    | MEAN_KEYWORD LPAR function_args RPAR
    | DOT_KEYWORD LPAR function_args RPAR

function_args: arithmetic_expression_level_1
    | function_args COMMA arithmetic_expression_level_1

function_decl: variable_expression LPAR function_decl_args RPAR EQ arithmetic_expression_level_1

function_decl_args: variable_expression COLON type
    | function_decl_args COMMA variable_expression COLON type

type: TYPE_COMPLEX
    | TYPE_FLOAT
    | TYPE_INT
    | TYPE_VECTOR
"""


def test_issue_1_exact_repro():
    text = 'complex_number = complex(2,3)'
    parser = Lark(GRAMMAR, parser='lalr', lexer='contextual', _plugins=lark_rust.plugins)
    tree = parser.parse(text)

    expected = Lark(GRAMMAR, parser='lalr', lexer='contextual').parse(text)
    assert tree == expected
