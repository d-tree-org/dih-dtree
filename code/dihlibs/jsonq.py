import re
from evaluator import evaluate;
import json

class JsonQ:
    PRIMITIVE_TYPES = {"string", "number", "boolean"}
    REGX = {
        "integer": re.compile(r"^\d+$"),
        "regular": re.compile(r"\w+(?:\.(?!\w*\*)\w+)*"),
        "array": re.compile(r"\[(?:(-?\d+:?-?\d*)|(\??\(.*\))|(\*))\]"),
        "array_bracket": re.compile(r"\[[^\]]+\]"),
        "globbed": re.compile(r"\w*\*\w*"),
        "wildcard": re.compile(r"\.{2,}(?:\.?\w+)*"),
        "expression": re.compile(r".*\[\??\(.*\)"),
        "variable": re.compile(r"@\.(\w+)"),
        "true": re.compile(r"yes|ndio|ndiyo|true", re.I),
        "false": re.compile(r"hapana|no|false", re.I),
        "date": re.compile(r"(?:\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|)")
    }

    @staticmethod
    def match(type, string):
        pattern=f'^{JsonQ.REGX[type].pattern}$'
        return bool(re.compile(pattern).match(string))

    @staticmethod
    def get_splitter():
        return re.compile(
            "|".join(f"({JsonQ.REGX[r].pattern})" for r in ["globbed", "regular", "wildcard", "array_bracket"]),
            re.VERBOSE
        )

    def __init__(self, json_obj):
        if isinstance(json_obj, str):
            self.root = json.loads(json_obj)
        else:
            self.root = json_obj

    def _evaluate_path(self, json_path):
        matched = re.finditer(JsonQ.get_splitter(), json_path)
        return [part for parts in matched for part in parts.groups() if part]

    def _collection_for_each(self, input, take):
        if isinstance(input, list):
            self.flat_for_each(input, take)
        else:
            take("", input)

    def get_object_root(self, obj):
        return obj if not isinstance(obj, JsonQ) else obj.root

    def handle_array_match(self, path, obj, results):
        parts = JsonQ.REGX["array"].match(path)
        if not parts:
            return

        if parts[3]:
            self._collection_for_each(obj, lambda _, v: results.append(v))
        elif parts[2]:
            self.filter(parts[2], obj, results)
        elif parts[1]:
            self._collection_for_each(obj, lambda _, v: results.append(v))
            self.slice_list(results, parts[1])

    def slice_list(self, lst, slice_notation):
        if not slice_notation:
            return

        slices = slice_notation.split(",")
        results = []
        for slice in slices:
            parts = slice.split(":")
            single_index = len(parts) == 1 and parts[0]
            length = len(lst)
            start = int(parts[0]) if len(parts) > 0 and parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else length
            start = max(start if start >= 0 else length + start, 0)
            end = start + 1 if single_index else min(end if end >= 0 else length + end, length)
            for i in range(start, end):
                results.append(lst[i])

        lst.clear()
        lst.extend(results)

    def is_primitive(self, data):
        return type(data).__name__ in JsonQ.PRIMITIVE_TYPES


    def filter(self, expression, object, results):
        def _filter_inner(key, obj):
            obj = self.get_object_root(obj)
            if isinstance(obj, dict):
                exp = expression
                for m in re.finditer(JsonQ.REGX["variable"], exp):
                    variable = m.group(1)
                    value = self.prep_variable_for_expression(obj.get(variable))
                    if value is None:
                        return
                    exp = exp.replace(f"@.{variable}", value)
                evaluation = evaluate(exp.replace("[]\\[]", ""))
            elif self.is_primitive(obj):
                value = self.prep_variable_for_expression(obj)
                if value is None:
                    return
                evaluation = evaluate(expression.replace("@." + key, value))
            else:
                evaluation = False
            if evaluation:
                results.append(obj)

        self._collection_for_each(object,_filter_inner)


    def prep_variable_for_expression(self, value):
        if not isinstance(value, str):
            return str(value) if self.is_primitive(value) else None

        if JsonQ.match("true", value):
            return "true"
        elif JsonQ.match("false", value):
            return "false"
        else:
            return f"'{value}'"

    def handle_normal_path(self, path, obj):
        if not path:
            return obj

        current = obj
        for p in path.split('.'):
            current = self.value_at_key(p, current)

        return None if current == obj else current

    def value_at_key(self, key, json_thing):
        if isinstance(json_thing, list) and key.isdigit():
            return json_thing[int(key)]
        elif isinstance(json_thing, dict):
            return json_thing.get(key)
        else:
            return json_thing

    def globbed_path(self, path, json_thing, results):
        self.flat_for_each(json_thing, lambda k, v: self._globbed_inner(path, k, v, results))

    def _globbed_inner(self, path, k, v, results):
        regex = re.compile(path.replace("*", "\\w*"))
        if regex.match(k):
            results.append(v)

    def find_matching_path(self, path, root, results):
        stack = [root]
        seen = set()
        path = re.sub(r"^[^\w*]+", "", path)

        while stack:
            current = stack.pop()
            res = self.handle_normal_path(path, current) if "*" not in path else self.globbed_path(path.replace("*", "\\w*"), current, results)
            self.flat_for_each(current, lambda key, obj: self._matching_inner(obj, stack, seen))

    def _matching_inner(self, obj, stack, seen):
        if obj is None or id(obj) in seen:
            return
        stack.append(obj)
        seen.add(id(obj))

    def flat_for_each(self, collection, callback):
        if isinstance(collection, list):
            for index, value in enumerate(collection):
                callback(index, value)
        elif isinstance(collection, dict):
            for key, value in collection.items():
                callback(key, value)
        elif collection is not None:
            callback("", collection)

    def find(self, json_path, root):
        results = []
        is_match = re.match(r"^(\.|)$", json_path)
        if is_match:
            return [root]
        if self.is_primitive(root):
            return results

        paths = self._evaluate_path(json_path)
        results.append(root)

        temp = []
        for path in paths:
            if not results:
                return results

            temp.clear()
            taker = None
            if JsonQ.match("regular", path):
                taker = lambda _, obj: temp.append(self.handle_normal_path(path, obj))
            elif JsonQ.match("globbed", path):
                taker = lambda _, obj: self.globbed_path(path, obj, temp)
            elif JsonQ.match("expression", path):
                taker = lambda _, obj: self.filter(path, obj, temp)
            elif JsonQ.match("wildcard", path):
                taker = lambda _, obj: self.find_matching_path(path, obj, temp)
            elif JsonQ.match("array", path):
                taker = lambda _, obj: self.handle_array_match(path, obj, temp)
            else:
                print(f"Path not found {json_path}. When processing this part {path}")
                return []

            self._collection_for_each(results, taker)
            results.clear()
            results.extend(temp)

        results.clear()
        results.extend([obj for obj in temp if obj])
        return results

    def get(self, path):
        return JsonQ(self.find(path, self.root))

    def put(self, path, value):
        i = path.rfind(".")
        prop = path[i + 1:]
        object_path = path[:i]
        self.flat_for_each(self.get(object_path).root, lambda _, obj: obj.update({prop: value}))

    def val(self):
        return self.root

    def for_each(self, callback):
        self.flat_for_each(self.root, lambda k, v: callback(k, JsonQ(v)))
