import re
from collections import deque
import json
import re
from typing import Any, Dict, List, Callable, Optional, Tuple
from functools import wraps
from datetime import datetime
import requests,os
import dihlibs.functions as fn
import yaml


class BoolEvaluator:
    def evaluate(self, expression: str) -> bool:
        """Evaluate a boolean expression."""
        postfix = self.to_postfix(expression)
        return self.evaluate_postfix(postfix)

    def to_postfix(self, infix: str) -> str:
        """Convert an infix expression to postfix notation."""
        output = []
        operators = deque()
        token_pattern = r'\d+\.?\d*|".*?"|\'.*?\'|[a-zA-Z]+|[+\-*/^<>!=&|~]+|[()]'
        tokens = re.findall(token_pattern, infix)

        for token in tokens:
            if re.match(r'\d+\.?\d*|".*?"|\'.*?\'|[a-zA-Z]+', token):
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
        tokens = re.compile(r'\d+\.?\d*|"[^"]*"|\'[^\']*\'|[a-zA-Z]+|[+\-*/^<>!=&|~]+').findall(postfix);
        for token in tokens:
            if token.lower() == "true":
                stack.append(1.0)
            elif token.lower() == "false":
                stack.append(0.0)
            elif re.match(r"\d+\.?\d*", token):
                stack.append(float(token))
            elif (token.startswith("'") and token.endswith("'")) or (token.startswith('"') and token.endswith('"')):
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
            b_val = self._coerce_to_bool(b)
            answer = 1.0 if b_val == 0 else 0.0
        else:
            b = stack.pop()
            a = stack.pop()
            if isinstance(a, float) and isinstance(b, float):
                answer = self.apply_operator(token, a, b)
            elif token in ("&&", "||"):
                a_bool = self._coerce_to_bool(a)
                b_bool = self._coerce_to_bool(b)
                answer = self.apply_operator(token, a_bool, b_bool)
            elif self.is_string_operator(token):
                answer = self.apply_string_operator(token, str(a), str(b))
            else:
                raise ValueError(
                    f"Unsupported operand types for operator: {token} operands {a} and {b}"
                )
        stack.append(answer)

    def _coerce_to_bool(self, value: Any) -> float:
        """Coerce different operand types into boolean-equivalent floats."""
        if isinstance(value, float):
            return value
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, int):
            return 1.0 if value != 0 else 0.0
        if isinstance(value, str):
            stripped = value.strip()
            lowered = stripped.lower()
            if lowered in ("", "false", "none", "null","[]","{}","()"):
                return 0.0
            try:
                return 0.0 if float(stripped) == 0 else 1.0
            except ValueError:
                return 1.0
        return 1.0 if value else 0.0

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
            return 1.0 if re.search(b, a) else 0.0
        else:
            raise ValueError(f"Unsupported operator for strings: {op}")


class JsonQ:
    # Regular expressions for path parsing
    _INTEGER = re.compile(r"^\d+$")
    _REGULAR_PATH = re.compile(r"\w+(?:\.\w+)*")
    _ARRAY = re.compile(
        r"\[(?:(\??\(.+\)|\s*[@\$].*)|(-?\d*:?-?\d*(?:,-?\d*:?-?\d*)*)|(\*)|(([`\"'])(.+?)\5))]"
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
    _VALUED_TRUE = re.compile(r"(?i)yes|ndio|ndiyo|true")
    _VALUED_FALSE = re.compile(r"(?i)hapana|no|false")

    _DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y"]

    def __init__(self, data: Any={}):
        """Initialize with raw JSON data."""
        self.root = data if not isinstance(data,JsonQ) else data.root
        self.bool_evaluator = BoolEvaluator()  # Add BoolEvaluator instance

    @staticmethod
    def _safe_constructor(*exceptions: Tuple[type, ...]):
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(cls, *args, **kwargs):
                handled_exceptions = exceptions or (Exception,)
                try:
                    return func(cls, *args, **kwargs)
                except handled_exceptions:
                    return cls("")
            return wrapper
        return decorator

    @classmethod
    @_safe_constructor(json.JSONDecodeError, TypeError)
    def from_json(cls, json_str: str) -> "JsonQ":
        """Create JsonQ from a JSON string."""
        return cls(json.loads(json_str))

    @classmethod
    @_safe_constructor(Exception)
    def from_file(cls, file_path: str) -> "JsonQ":
        """Create JsonQ from a file."""
        return cls(fn.load_file_data(file_path))

    @classmethod
    @_safe_constructor(Exception)
    def from_folder(cls, folder: str) -> "JsonQ":
        """Create JsonQ from a folder."""
        return cls([ fn.load_file_data(f'{folder}/{file}')
               for file in os.listdir(f'{folder}') 
        ])

    @classmethod
    @_safe_constructor(requests.RequestException, json.JSONDecodeError, ValueError)
    def from_url(cls, url: str, *args, **kwargs) -> "JsonQ":
        """Create JsonQ from a URL."""
        response = requests.get(url, timeout=10,*args,**kwargs)
        response.raise_for_status()
        return cls(response.json())

    @classmethod
    def from_response(cls, response) -> "JsonQ":
        """Create JsonQ from a requests-like response object."""
        if response is None:
            return cls("")
        json_loader = getattr(response, "json", None)
        if callable(json_loader):
            try:
                return cls(json_loader())
            except (ValueError, json.JSONDecodeError):
                pass
        text = getattr(response, "text", "")
        return cls(text if text is not None else "")

    @classmethod
    @_safe_constructor(Exception)
    def from_secret(cls, filename:str,overwrite=False):
        return cls(fn.load_secret_file(filename,overwrite))

    @classmethod
    @_safe_constructor(TypeError, json.JSONDecodeError)
    def from_object(cls, obj: Any) -> "JsonQ":
        """Create JsonQ from a Python object."""
            
        if cls._is_json_primitive(obj):
            return cls(obj)
        if isinstance(obj,JsonQ):
            return JsonQ.from_object(obj.root)
        return cls(json.loads(json.dumps(obj)))

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
            for x in self._find(path)
            if isinstance(x, (int, str)) and str(x).isdigit()
        ]

    def int(self, path):
        return int(self.str(path))

    def str(self, path):
        res=self._find(path)
        if len(res)==1:
            return str(res[0])
        else: return self._from_results(res).to_string()

    def value(self, path):
        res=self._find(path)
        if len(res)==1:
            return res[0]
        else: return res

    def to_string(self,indent=None):
        if isinstance(self.root,str):
            return self.root
        return json.dumps(self.root,indent=indent, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o))

    def dumps(self,indent=None):
        return self.to_string(indent)

    def print(self,indent=None):
        print(self.to_string(indent))

    def printy(self,indent=None):
        print(yaml.dump(self.root,indent=indent))

    def get(self, path):
        return self._from_results(self._find(path))

    def find(self, path):
        return self._from_results(self._find(path)).root

    def _find(self, json_path: str) -> List[Any]:
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
        context = obj if not isinstance(obj,JsonQ) else obj.root
        # exp = re.findall(r"\((.*)\)", expression) 
        exp = expression #if not exp else exp[0]

        if re.fullmatch(r'\s*[@$]\s*',exp):
            exp=str(bool(context)).lower()
        
        self._flat_for_each(
            context, lambda k, v: self._evaluate_filter(exp, v, results)
        )
        return results

    def _evaluate_filter(
        self, expression: str, obj: Any, results: List[Any]
    ) -> None:
        """Evaluate filter expression."""
        exp=expression
        ctx=JsonQ.from_object(obj)
        

        """Replace @.path references with their evaluated values."""
        while var:=re.search(r'[@$](\.?[.\w\(\)"\'\[\}\]]+)?',exp):
            path=var[1] or ''
            value=ctx.get(path.strip()).val()
            if self._is_json_primitive(value) or not value:
                prepared = self._prep_variable_for_expression(value)
                exp=exp.replace(var[0],prepared)
            else :
                 matches=self._evaluate_complex(ctx,exp)
                 exp=str(matches).lower()

        if self.bool_evaluator.evaluate(exp):
            results.append(obj)


    def _evaluate_complex(self,obj,expression):        
        var=re.findall(r'([@$](?:\.?[.\w\(\)"\'\[\}\]]+)?)',expression)
        zote={k:sorted(list(set(obj.get(k).leaves().values()or [None]))) for k in var}
        n=1
        for k,v in zote.items():
            n=n*len(v)
        answer=False
        for i in range(n):
            row=fn.cartesian_row(zote.values(),i)
            expr=expression;
            for j,k in enumerate(zote.keys()):
                prepared = self._prep_variable_for_expression(row[j])
                expr=expr.replace(k,prepared)
            answer= answer or self.bool_evaluator.evaluate(expr)
        return answer;


    def _evaluate_filter_many(self,exp,path,value):
        prepared=self._prep_variable_for_expression(value)
        exp=exp.replace(path,prepared)
        return self.bool_evaluator.evaluate(exp)


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
            if current is not obj  and p.endswith(path):
                results.append(current)

    def get_strings(self, json_path: str = "[*]") -> List[str]:
        """Extract strings from a path."""
        return [
            json.dumps(x) if not isinstance(x, str) else x for x in self._find(json_path)
        ]

    def int_column(self, column_name: str) -> List[int]:
        """Extract integers from a column."""
        path = f"[(@.{column_name}~'\\d+')]"
        return [
            int(x)
            for x in self._find(path)
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

    def change(self,path,func):
        self.put(path,func(self.get(path).root))
        
    def put(self, json_path: str, value: Any,override=True) -> None:
        """Put a value at the specified path."""
        match=re.search(r'(\["[^"]*."\]|(?<=\.)[^.\]]+|^[^.\]]+)$',json_path)
        if not match:
            return
        field=re.sub(r'(^[\s"\[]+|[\s"\]]+$)','',match.group(0))
        path=json_path[:match.start()]
        res = self._find(path) if path else [self.root]
        self._flat_for_each(
            res, lambda k, v: self._put_in_container(override, v, field, value)
        )

    def add(self, json_path: str, value: Any) -> None:
        """Add a value to the root."""
        targets = self._find(json_path)
        appended = False
        for target in targets:
            container = self._get_object_root(target)
            if isinstance(container, list):
                container.append(value)
                appended = True
        if not appended:
            self.put(json_path, value, False)

    def merge(self, json_path: str, value: Any, list_policy: str = "extend") -> None:
        """Merge value into the node(s) at the specified path."""
        helper = self._MergeContext(self, value, list_policy)
        if helper.merge_existing(json_path):
            return
        for container, field in helper.parent_targets(json_path):
            helper.merge_into(container, field)

    def merge_many(self, mapping: Dict[str, Any], *, list_policy: str = "extend") -> None:
        """Apply multiple merge operations from a path-value mapping."""
        if not isinstance(mapping, dict):
            raise TypeError("merge_many expects a mapping of json paths to values")
        for path, value in mapping.items():
            resolved_path = "" if path is None else path
            self.merge(resolved_path, value, list_policy=list_policy)

    class _MergeContext:
        _FIELD_PATTERN = re.compile(r'(\["[^"]*."\]|(?<=\.)[^.\]]+|^[^.\]]+)$')

        def __init__(self, owner: "JsonQ", value: Any, list_policy: str):
            self.owner = owner
            self.value = value
            self.list_policy = list_policy

        def merge_existing(self, json_path: str) -> bool:
            try:
                nodes = self.owner._find(json_path)
            except Exception:
                return False
            merged = False
            for node in nodes:
                target = self.owner._get_object_root(node)
                if isinstance(target, (dict, list)):
                    self.owner._merge_values(target, self.value, self.list_policy)
                    merged = True
            return merged

        def parent_targets(self, json_path: str):
            match = self._FIELD_PATTERN.search(json_path or "")
            if not match:
                yield self.owner.root, None
                return
            raw_field = match.group(0)
            field = re.sub(r'(^[\s"\[]+|[\s"\]]+$)', "", raw_field)
            parent_path = json_path[: match.start()]
            try:
                containers = (
                    self.owner._find(parent_path) if parent_path else [self.owner.root]
                )
            except Exception:
                containers = []
            for container in containers:
                yield self.owner._get_object_root(container), field

        def merge_into(self, container: Any, field: Optional[str]) -> None:
            if isinstance(container, dict):
                self._merge_dict(container, field)
            elif isinstance(container, list):
                self._merge_list(container, field)

        def _merge_dict(self, container: Dict[str, Any], field: Optional[str]) -> None:
            if not field:
                self.owner._merge_values(container, self.value, self.list_policy)
                return
            if field not in container or container[field] is None:
                container[field] = self.value
            else:
                container[field] = self.owner._merge_values(
                    container[field], self.value, self.list_policy
                )

        def _merge_list(self, container: List[Any], field: Optional[str]) -> None:
            if not field:
                self.owner._merge_into_list(container, self.value, self.list_policy)
                return
            if self.owner._INTEGER.match(field):
                idx = int(field)
                if 0 <= idx < len(container):
                    container[idx] = self.owner._merge_values(
                        container[idx], self.value, self.list_policy
                    )
                    return
            self.owner._merge_into_list(container, self.value, self.list_policy)

    def _merge_values(self, target: Any, incoming: Any, list_policy: str) -> Any:
        """Merge incoming value into target, returning the merged value."""
        target_root = self._get_object_root(target)
        incoming_root = self._get_object_root(incoming)

        if isinstance(target_root, dict) and isinstance(incoming_root, dict):
            for key, value in incoming_root.items():
                if key in target_root and isinstance(target_root[key], (dict, list)) and isinstance(value, (dict, list)):
                    target_root[key] = self._merge_values(target_root[key], value, list_policy)
                else:
                    target_root[key] = value
            return target_root

        if isinstance(target_root, list):
            self._merge_into_list(target_root, incoming_root, list_policy)
            return target_root

        return incoming_root

    def _merge_into_list(self, target: List[Any], incoming: Any, list_policy: str) -> None:
        """Merge incoming value into list according to policy."""
        if list_policy == "replace" and isinstance(incoming, list):
            target.clear()
            target.extend(incoming)
            return

        if isinstance(incoming, list):
            if list_policy == "append":
                target.append(incoming)
            else:  # default extend
                target.extend(incoming)
        else:
            target.append(incoming)

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
            json.dumps(self.root,indent=2, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o))
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
            return "null"
        if isinstance(val, (int, float, bool)):
            return str(val).lower()
        if isinstance(val, str):
            if self._VALUED_TRUE.match(val):
                return "true"
            if self._VALUED_FALSE.match(val):
                return "false"
            return json.dumps(val)
        return "null"

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

    def leaves(self,path='',predicateFunc=lambda p,current:True):
        """Handle wildcard paths."""
        obj=self.get(path).root
        if self._is_json_primitive(obj) and predicateFunc(path,obj):
            return {path:obj}
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
    
