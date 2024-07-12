import re

arithmetic_ops = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
}

comparison_ops = {
    ">": lambda a, b: 1.0 if a > b else 0.0,
    "<": lambda a, b: 1.0 if a < b else 0.0,
    "==": lambda a, b: 1.0 if a == b else 0.0,
    "!=": lambda a, b: 1.0 if a != b else 0.0,
    ">=": lambda a, b: 1.0 if a >= b else 0.0,
    "<=": lambda a, b: 1.0 if a <= b else 0.0,
}

logical_ops = {
    "&": lambda a, b: 1.0 if (a != 0 and b != 0) else 0.0,
    "&&": lambda a, b: 1.0 if (a != 0 and b != 0) else 0.0,
    "|": lambda a, b: 1.0 if (a != 0 or b != 0) else 0.0,
    "||": lambda a, b: 1.0 if (a != 0 or b != 0) else 0.0,
}

operations = {**arithmetic_ops, **comparison_ops, **logical_ops}


def _handle_operator(output, operators, token):
    while operators and _precedence(operators[-1]) >= _precedence(token):
        output += operators.pop() + " "
    operators.append(token)
    return output


def _handle_parenthesis(output, operators, parenthesis):
    if parenthesis == "(":
        operators.append(parenthesis)
    elif parenthesis == ")":
        while operators and operators[-1] != "(":
            output += operators.pop() + " "
        if operators and operators[-1] == "(":
            operators.pop()
    return output


def _precedence(operator):
    return {
        "+": 1, "-": 1, "*": 2, "/": 2,
        "^": 3, "<": 4, ">": 4, "<=": 4,
        ">=": 4, "==": 4, "!=": 4, "!": 4, "~": 4,
    }.get(operator, -1)


def _is_operator(token):
    return bool(re.match(r"^[+\-*/^<>!=&|~]+$", token))


def _is_string_operator(token):
    return bool(re.match(r"^[<>=~!]+$", token))


def _apply_operator(op, a, b):
    if op in operations:
        return operations[op](a, b)
    else:
        raise ValueError(f"Unsupported operator: {op}")


def _apply_string_operator(op, a, b):
    if op in operations:
        return operations[op](a, b)
    elif op=="~": 
        return 1.0 if re.search(b, a) else 0.0
    else:
        raise ValueError(f"Unsupported operator for strings: {op}")


def _to_postfix(infix):
    output = ""
    operators = []
    token_pattern = re.compile(r"\d+\.?\d*|'[^']*'|[a-zA-Z]+|[+\-*/^<>!=&|~]+|[()]")

    for m in token_pattern.finditer(infix):
        token = m.group(0)
        if re.match(r"^(?:\d+\.?\d*|'[^']*'|[a-zA-Z]+)$", token):
            output += token + " "
        elif token in (")", "("):
            output = _handle_parenthesis(output, operators, token)
        elif _is_operator(token):
            output = _handle_operator(output, operators, token)
        else:
            raise ValueError(f"Unexpected token: {token}")

    while operators:
        output += operators.pop() + " "

    return output


def _evaluate_postfix(postfix):
    stack = []
    token_pattern = re.compile(r"\d+\.?\d*|'[^']*'|[a-zA-Z]+|[+\-*/^()<>!=&|~]+")

    for m in token_pattern.finditer(postfix):
        token = m.group(0)
        if token in ['true','false']:
            stack.append(1.0 if token=="true" else 0)
        elif re.match(r"^\d+\.?\d*$", token):
            stack.append(float(token))
        elif re.match(r"^'[^']*'$", token):
            stack.append(token[1:-1])
        elif _is_operator(token):
            _operate(token, stack)
        elif re.match(r"^\w+$", token):
            stack.append(token)
        else:
            raise ValueError(f"Unexpected token: {token}")
    return stack.pop() == 1.0

def _operate(token, stack):
    b = stack.pop()
    answer = None

    if token == "!" and isinstance(b, float):
        answer = 1.0 if b == 0 else 0.0
    else:
        a = stack.pop()
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            answer = _apply_operator(token, a, b)
        elif _is_string_operator(token):
            answer = _apply_string_operator(token, a, b)
        else:
            answer = None

    if answer == None:  # Check for NaN
        error = f"Unsupported operand type for operator: {token} operand {a} and {b}"
        print(error, token, a, b)
    stack.append(answer)


def evaluate(expression):
    return _evaluate_postfix(_to_postfix(expression))

