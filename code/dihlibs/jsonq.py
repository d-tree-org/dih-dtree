import re
from collections import deque
import json
import re
from typing import Any, List, Callable, Optional
from datetime import datetime
import requests
import dihlibs.functions as fn


class BoolEvaluator:
    def evaluate(self, expression: str) -> bool:
        """Evaluate a boolean expression."""
        postfix = self.to_postfix(expression)
        return self.evaluate_postfix(postfix)

    def to_postfix(self, infix: str) -> str:
        """Convert an infix expression to postfix notation."""
        output = []
        operators = deque()
        token_pattern = r"\d+\.?\d*|'.*?'|[a-zA-Z]+|[+\-*/^<>!=&|~]+|[()]"
        tokens = re.findall(token_pattern, infix)

        for token in tokens:
            if re.match(r"\d+\.?\d*|'.*?'|[a-zA-Z]+", token):
                output.append(token)
            elif token == "(" or token == ')':
                self._handle_brackets(output,operators,token)
            elif self.is_operator(token):
                self._handle_operator(output,operators,token)
            else:
                raise ValueError(f"Unexpected token: {token}")

        while operators:
            output.append(operators.pop())

        return " ".join(output)

    def evaluate_postfix(self, postfix: str) -> bool:
        """Evaluate a postfix expression."""
        stack = []
        tokens = re.compile(r"\d+\.?\d*|'[^']*'|[a-zA-Z]+|[+\-*/^<>!=&|~]+").findall(postfix);
        for token in tokens:
            if token.lower() == "true":
                stack.append(1.0)
            elif token.lower() == "false":
                stack.append(0.0)
            elif re.match(r"\d+\.?\d*", token):
                stack.append(float(token))
            elif token.startswith("'") and token.endswith("'"):
                stack.append(token[1:-1])
            elif self.is_operator(token):
                self.operate(token, stack)
            elif re.match(r"\w+", token):
                stack.append(token)
            else:
                raise ValueError(f"Unexpected token: {token}")
        return stack.pop() == 1.0
    
    def _handle_brackets(self,output,operators,token):
        if token == "(": operators.append(token); return
        elif token == ")":
            while operators and operators[-1] != "(":
                output.append(operators.pop())
            if operators and operators[-1] == "(":
                operators.pop()

    def _handle_operator(self,output,operators,token):
        while (operators and operators[-1] != '(' 
               and  self.precedence(operators[-1]) >= self.precedence(token)):
               output.append(operators.pop())
        operators.append(token)

    def operate(self, token: str, stack: list):
        """Apply an operator to operands from the stack."""
        if token == "!":
            b = stack.pop()
            if isinstance(b, float):
                answer = 1.0 if b == 0 else 0.0
            else:
                raise ValueError(
                    f"Unsupported operand type for operator: {token} operand {b}"
                )
        else:
            b = stack.pop()
            a = stack.pop()
            if isinstance(a, float) and isinstance(b, float):
                answer = self.apply_operator(token, a, b)
            elif self.is_string_operator(token):
                answer = self.apply_string_operator(token, str(a), str(b))
            else:
                raise ValueError(
                    f"Unsupported operand types for operator: {token} operands {a} and {b}"
                )
        stack.append(answer)

    def is_operator(self, token: str) -> bool:
        """Check if a token is an operator."""
        return re.match(r"[+\-*/^<>!=&|~]+", token) is not None

    def is_string_operator(self, token: str) -> bool:
        """Check if a token is a string-compatible operator."""
        return re.match(r"[<>=~!]+", token) is not None

    def precedence(self, operator: str) -> int:
        """Determine the precedence of an operator."""
        if operator in "+-":
            return 1
        elif operator in "*/":
            return 2
        elif operator == "^":
            return 3
        elif operator in "<><=>===!=!~":
            return 4
        return -1

    def apply_operator(self, op: str, a: float, b: float) -> float:
        """Apply a numeric operator to two operands."""
        if op == "+":
            return a + b
        elif op == "-":
            return a - b
        elif op == "*":
            return a * b
        elif op == "/":
            return a / b
        elif op == ">":
            return 1.0 if a > b else 0.0
        elif op == "<":
            return 1.0 if a < b else 0.0
        elif op == "==" or op == "=":
            return 1.0 if a == b else 0.0
        elif op == "!=":
            return 1.0 if a != b else 0.0
        elif op == ">=":
            return 1.0 if a >= b else 0.0
        elif op == "<=":
            return 1.0 if a <= b else 0.0
        elif op == "&" or op == "&&":
            return 1.0 if a != 0 and b != 0 else 0.0
        elif op == "|" or op == "||":
            return 1.0 if a != 0 or b != 0 else 0.0
        else:
            raise ValueError(f"Unsupported operator: {op}")

    def apply_string_operator(self, op, a: str, b: str) -> float:
        """Apply a string operator to two operands."""
        if op == "==" or op == "=":
            return 1.0 if a == b else 0.0
        elif op == "!=":
            return 1.0 if a != b else 0.0
        elif op == ">":
            return 1.0 if a > b else 0.0
        elif op == "<":
            return 1.0 if a < b else 0.0
        elif op == ">=":
            return 1.0 if a >= b else 0.0
        elif op == "<=":
            return 1.0 if a <= b else 0.0
        elif op == "~":
            return 1.0 if re.match(b, a) else 0.0
        else:
            raise ValueError(f"Unsupported operator for strings: {op}")


class JsonQ:
    # Regular expressions for path parsing
    _INTEGER = re.compile(r"^\d+$")
    _REGULAR_PATH = re.compile(r"\w+(?:\.\w+)*")
    _ARRAY = re.compile(
        r"\[(?:(\??\(.+\))|(-?\d*:?-?\d*(?:,-?\d*:?-?\d*)*)|(\*)|(([`\"'])(.+?)\5))]"
    )
    _GLOBED_PATH = re.compile(r"(?=.*\*)(?=.*\w)[^.\[\]()?'\"]*")
    _WILDCARD = re.compile(r"\.{2,3}(?:" + _REGULAR_PATH.pattern + ")?")
    _PATH_EXPRESSION = re.compile(r".*\[?\??\(.*\)")
    _PATH_POSSIBILITIES = re.compile(
        r"((?=.*\*)(?=.*\w)[^.\[\]()?'\"]*)?"  # First capturing group: optional wildcard conditions
        r"((?:\w+|\"[^\"]+\")(?:\.(?:\w+|\"[^\"]+\"))*)?"  # Second capturing group: matches words or quoted strings with dots
        r"(\.{2,3}(?:"  # Third capturing group: matches ".." or "..."
        r"(?:\w+|\"[^\"]+\")(?:\.(?:\w+|\"[^\"]+\"))*)?)?"  # Optional word or quoted string with dots
        r"(\[[^]]+])?"  # Fourth capturing group: matches brackets with content inside
    )
    _JSON_VARIABLE = re.compile(r"@\.(\w+)")
    _VALUED_TRUE = re.compile(r"(?i)yes|ndio|ndiyo|true")
    _VALUED_FALSE = re.compile(r"(?i)hapana|no|false")

    _DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y"]

    def __init__(self, data: Any={}):
        """Initialize with raw JSON data."""
        self.root = data if not isinstance(data,JsonQ) else data.root
        self.bool_evaluator = BoolEvaluator()  # Add BoolEvaluator instance

    @classmethod
    def from_json(cls, json_str: str) -> "JsonQ":
        """Create JsonQ from a JSON string."""
        try:
            return cls(json.loads(json_str))
        except json.JSONDecodeError:
            return cls("")

    @classmethod
    def from_file(cls, file_path: str) -> "JsonQ":
        """Create JsonQ from a file."""
        return cls(fn.load_file_data(file_path))

    @classmethod
    def from_url(cls, url: str, *args, **kwargs) -> "JsonQ":
        """Create JsonQ from a URL."""
        try:
            response = requests.get(url, timeout=10,*args,**kwargs)
            response.raise_for_status()
            return cls(response.json())
        except (requests.RequestException, json.JSONDecodeError):
            return cls("")

    @classmethod
    def from_object(cls, obj: Any) -> "JsonQ":
        """Create JsonQ from a Python object."""
        if cls._is_json_primitive(obj):
            return cls(obj)
        try:
            return cls(json.loads(json.dumps(obj)))
        except (TypeError, json.JSONDecodeError):
            return cls(obj)

    def to_file(self, file_path: str) -> bool:
        """Write JSON data to a file."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.root, f, indent=2)
            return True
        except IOError:
            return False

    def integers(self, path):
        self.get(path)
        return [
            int(x)
            for x in self.find(path)
            if isinstance(x, (int, str)) and str(x).isdigit()
        ]

    def int(self, path):
        return int(self.str(path))

    def str(self, path):
        res=self.find(path)
        if len(res)==1:
            return str(res[0])
        else: return self._from_results(res).to_string()

    def value(self, path):
        res=self.find(path)
        if len(res)==1:
            return res[0]
        else: return res

    def to_string(self):
        return json.dumps(self.root)

    def get(self, path):
        return self._from_results(self.find(path))

    def find(self, json_path: str) -> List[Any]:
        """Find all elements matching the given JSON path."""
        if not json_path or json_path == ".":
            return [self.root]
        if self._is_json_primitive(self.root):
            return []

        paths = self._evaluate_path(json_path)
        results = [self.root]
        temp = []
        for path in paths:
            if not results:
                return results
            temp.clear()
            if self._REGULAR_PATH.fullmatch(path):
                self._flat_for_each(
                    results, lambda k, v: temp.append(self._handle_normal_path(path, v))
                )
            elif self._GLOBED_PATH.fullmatch(path):
                self._flat_for_each(
                    results, lambda k, v: self._globed_path(path, v, temp)
                )
            elif self._PATH_EXPRESSION.fullmatch(path):
                self._flat_for_each(results, lambda k, v: self._filter(path, v, temp))
            elif self._WILDCARD.fullmatch(path):
                self._flat_for_each(
                    results, lambda k, v: self._find_matching_path(path,v, temp)
                )
            elif self._ARRAY.fullmatch(path):
                self._flat_for_each(
                    results, lambda k, v: self._handle_array_match(path, v, temp)
                )
            else:
                print(f"Path not found: {json_path}. When processing part: {path}")
                return []

            results = [x for x in temp if x is not None]
        return results

    def _evaluate_path(self, json_path: str) -> List[str]:
        """Split the path into components."""
        json_path = re.sub(r"^$\.?", "", json_path)
        matcher = self._PATH_POSSIBILITIES.finditer(json_path)
        paths = []
        for match in matcher:
            for group in match.groups():
                if group and group.strip():
                    paths.append(group)
        return paths

    def _handle_normal_path(self, path: str, obj: Any) -> Any:
        """Handle dot-separated paths."""
        current = obj
        for p in path.split("."):
            current = self._value_at_key(p, current)
            if current is None:
                break
        return current if current != obj else None

    def _globed_path(self, path: str, obj: Any, results: List[Any]) -> None:
        """Handle glob patterns."""
        pattern = path.replace("*", r"\w*")
        self._flat_for_each(
            obj, lambda k, v: results.append(v) if re.fullmatch(pattern, k) else None
        )

    def _handle_array_match(self, path: str, obj: Any, results: List[Any]) -> None:
        """Handle array access."""
        matcher = self._ARRAY.match(path)
        if not matcher:
            return
        group1, group2, group3, group4, group5, group6 = matcher.groups()
        if group3:  # [*]
            self._flat_for_each(obj, lambda k, v: results.append(v))
        elif group1:  # [?(condition)]
            self._filter(group1, obj, results)
        elif group2:  # [start:end] or [index]
            temp = []
            self._flat_for_each(obj, lambda k, v: temp.append(v))
            self._slice_list(temp, group2)
            results.extend(temp)
        elif group6:
            if isinstance(obj,List) and len(obj)==1:
               obj=obj[0] 
            results.append(self._value_at_key(group6, obj))

    def _slice_list(self, lst: List[Any], slice_notation: str) -> None:
        """Apply array slicing."""
        result = []
        for slice_part in slice_notation.split(","):
            parts = slice_part.split(":")
            if len(parts) == 1 and parts[0]:
                idx = int(parts[0])
                idx = idx if idx >= 0 else len(lst) + idx
                if 0 <= idx < len(lst):
                    result.append(lst[idx])
            else:
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if len(parts) > 1 and parts[1] else len(lst)
                start = max(start if start >= 0 else len(lst) + start, 0)
                end = min(end if end >= 0 else len(lst) + end, len(lst))
                result.extend(lst[start:end])
        lst.clear()
        lst.extend(result)

    def _filter(self, expression: str, obj: Any, results: List[Any]) -> None:
        """Filter objects based on an expression."""
        expression = re.findall(r"\((.*)\)", expression)[0]
        self._flat_for_each(
            obj, lambda k, v: self._evaluate_filter(expression, k, v, results)
        )

    def _evaluate_filter(
        self, expression: str, key: str, obj: Any, results: List[Any]
    ) -> None:
        """Evaluate filter expression."""
        obj = self._get_object_root(obj)
        if isinstance(obj, dict):
            exp = expression
            for match in self._JSON_VARIABLE.finditer(exp):
                var = match.group(1)
                val = self._prep_variable_for_expression(obj.get(var))
                if val is None:
                    return
                exp = exp.replace(f"@.{var}", val)
            if self._evaluate_bool(exp):
                results.append(obj)
        elif self._is_json_primitive(obj) and key:
            val = self._prep_variable_for_expression(obj)
            if val and self._evaluate_bool(expression.replace(f"@.{key}", val)):
                results.append(obj)

    def _evaluate_bool(self, expression: str) -> bool:
        """Evaluate a boolean expression using BoolEvaluator."""
        try:
            return self.bool_evaluator.evaluate(expression)
        except Exception as e:
            print(f"Error evaluating expression: {expression}, error: {e}")
            return False

    def _find_matching_path(self,path, obj: Any, results: List[Any]) -> None:
        """Handle wildcard paths."""
        seen = set()
        path = path.lstrip('.')
        stack = [('',obj)]
        while stack:
            p,current = stack.pop()
            p=p.strip('.')
            if p in seen:
                continue
            seen.add(p)
            self._flat_for_each(
                current, lambda k, v: stack.append((f'{p}.{k}',v)) if v is not None else None
            )
            if current != obj and path in p:
                results.append(current)

    def get_strings(self, json_path: str = "[*]") -> List[str]:
        """Extract strings from a path."""
        return [
            json.dumps(x) if not isinstance(x, str) else x for x in self.find(json_path)
        ]

    def int_column(self, column_name: str) -> List[int]:
        """Extract integers from a column."""
        path = f"[(@.{column_name}~'\\d+')]"
        return [
            int(x)
            for x in self.find(path)
            if isinstance(x, (int, str)) and str(x).isdigit()
        ]

    def date_column(self, column_name: str) -> List[datetime]:
        """Extract dates from a column."""
        path = f"[(@.{column_name}~'\\d{{2,4}}-\\d{{2}}-\\d{{2,4}}')].{column_name}"
        return self.get_dates(path)

    def get_dates(self, json_path: str) -> List[datetime]:
        """Parse dates from a path."""
        dates = []
        for d in self.get_strings(json_path):
            date = self._parse_date(d)
            if date:
                dates.append(date)
        return dates

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string."""
        for fmt in self._DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def select(self, *columns: str) -> "JsonQ":
        """Select specific columns."""
        results = []
        def visit(k, v):
          if isinstance(v, dict):
                jq = JsonQ(v)
                selected = {}
                for col in columns:
                    # split on ' as ', case‐insensitive
                    parts = re.split(r'\s+as\s+', col, flags=re.IGNORECASE)
                    expr = parts[0]
                    alias = parts[1] if len(parts) > 1 else expr
                    val = jq.get(expr).val()
                    selected[alias] = val
                results.append(selected)
        self._flat_for_each(self.root, visit)
        return self._from_results([r for r in results if r])


    def where(self, condition: str, *values: Any) -> "JsonQ":
        """Filter data based on a condition."""
        exp = (
            condition.replace(" and ", "&&")
            .replace(" or ", "||")
            .replace(r"\b(\w+)\b", r"@.\1")
            .replace("=", "==")
        )
        for v in values:
            if not self._is_json_primitive(v):
                continue
            val = f"'{v}'" if isinstance(v, str) else str(v)
            exp = exp.replace("?", val, 1)
        exp = f"({exp})"
        results = []
        self._filter(exp, self.root, results)
        return self._from_results(results)

    def put(self, json_path: str, value: Any,override=True) -> None:
        """Put a value at the specified path."""
        match=re.search(r'(\["[^"]*."\]|(?<=\.)[^.\]]+|^[^.\]]+)$',json_path)
        if not match:
            return
        field=re.sub(r'(^[\s"\[]+|[\s"\]]+$)','',match.group(0))
        path=json_path[:match.start()]
        res = self.find(path) if path else [self.root]
        self._flat_for_each(
            res, lambda k, v: self._put_in_container(override, v, field, value)
        )

    def add(self, json_path: str, value: Any) -> None:
        """Add a value to the root."""
        self.put(json_path,value,False)

    def _put_in_container(
        self, override: bool, container: Any, key: str, value: Any
    ) -> None:
        """Put value into a container."""
        if isinstance(container, dict):
            if not key or (key not in container or override):
                container[key or ""] = value
        elif isinstance(container, list):
            if self._INTEGER.match(key):
                idx = int(key)
                if 0 <= idx < len(container) and override:
                    container[idx] = value
                else:
                    container.append(value)
            else:
                container.append(value)

    def val(self) -> Any:
        """Return the raw root data."""
        return self.root if self.root != [] else None

    def is_empty(self) -> bool:
        """Check if the data is empty."""
        if self.root is None:
            return True
        if isinstance(self.root, (dict, list)):
            return len(self.root) == 0
        if isinstance(self.root, str):
            return not self.root
        return False

    def __str__(self) -> str:
        """String representation."""
        return (
            json.dumps(self.root, indent=2)
            if not isinstance(self.root, str)
            else self.root
        )

    def for_each(self, callback: Callable[["str", "JsonQ"], None]) -> None:
        """Iterate over the data."""
        self._flat_for_each(
            self.root, lambda k, v: callback(k, JsonQ(v)) if v != self.root else None
        )

    @staticmethod
    def _is_json_primitive(obj: Any) -> bool:
        """Check if an object is a JSON primitive."""
        return isinstance(obj, (int, float, str, bool))

    @staticmethod
    def _get_object_root(obj: Any) -> Any:
        """Get the root object."""
        return obj.root if isinstance(obj, JsonQ) else obj

    def _prep_variable_for_expression(self, val: Any) -> Optional[str]:
        """Prepare a value for expression evaluation."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, str):
            if self._VALUED_TRUE.match(val):
                return "true"
            if self._VALUED_FALSE.match(val):
                return "false"
            return f"'{val}'"
        return None

    def _value_at_key(self, key: str, obj: Any) -> Any:
        """Access a value by key or index."""
        if isinstance(obj, dict):
            return obj.get(key)
        if isinstance(obj, list) and self._INTEGER.match(key):
            idx = int(key)
            return obj[idx] if 0 <= idx < len(obj) else None
        return None

    def _flat_for_each(self, obj: Any, consumer: Callable[[str, Any], None]) -> None:
        """Iterate over a collection."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v is not None:
                    consumer(str(k), v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if v is not None:
                    consumer(str(i), v)
        elif obj is not None:
            consumer("", obj)

    def _from_results(self, results: List[Any]) -> "JsonQ":
        """Create a new JsonQ from query results."""
        results = [x for x in results if x is not None]
        if len(results) == 1:
            return JsonQ(results[0])
        return JsonQ(results if results else [])
    

    def keys(self,path='',predicateFunc=None,trimmed=False):
        data=self.leaves(path,predicateFunc=predicateFunc)
        if trimmed:
            data = {re.sub(r".+\.(\w+)$", r"\1", key): value for key, value in data.items()}
        return list(data.keys())

    def leaves(self,path='',predicateFunc=None):
        """Handle wildcard paths."""
        obj=self.get(path).root
        res={}
        seen = set()
        stack = [(obj,path)]
        while stack:
            current,p = stack.pop()
            p=p.strip('.')
            if p in seen:
                continue
            seen.add(p)
            self._flat_for_each(
                current, lambda k, v: stack.append((v,f'{p}.{k}')) if v is not None else None
            )

            if current != obj and self._is_json_primitive(current):
                if predicateFunc is None or predicateFunc(p,current):
                    res[p.lstrip('.')]=current
        return res    

    def fill_template(self, template=None, file=None):
        jq=JsonQ(template) if template is not None else JsonQ.from_file(file)
        leaves=jq.leaves(predicateFunc=lambda _,v: v and '$' == v[0])
        for k,v in leaves.items():
            p=re.sub(r'\$?([^.]+)\.?',r'["\1"]',v)
            key=re.sub(r'\$?([^.]+)\.?',r'["\1"]',k)
            value=self.value(p) or None
            jq.put(key,value)
        return jq.root
