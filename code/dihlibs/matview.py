import re, yaml
from glob import glob
import dihlibs.functions as fn
from pathlib import Path
from dihlibs.jsonq import JsonQ
from collections import Counter


PLACE_HOLDER = "==>><<badilisha"
COLUMN_NAME = r"\b([a-z_][.\w]*)(?:,(?![^\(]+\)|[^\{]+\})|\s*$)"
COLUMN = re.compile(rf"(?i)(.*?)(?:\b\s*as\s+)?{COLUMN_NAME}", re.DOTALL)
CTE_RGX = re.compile(r"(?isx)(?:with|,)?\s*(\w+)\s+as\s*(?=\()")
VIEW_RGX = re.compile(
    r"(?isx)\bcreate\s+(materialized\s+)?view\s+([\w\.]+)\s+as\s*\(([^;]+?)\)\s*;"
)
TABLE_NAME_RGX = re.compile(
    r"(?isx)\s+(?:from|join)\s+([A-z_][\w.]+)\s*(?:as\b)(?:\s+([\w.]+))"
)
SELECT_RGX = re.compile(
    r"(?isx)(?<!['\"])select(.*?)((?<![\"'])from(?![^\(]+\)|[^\{]+\})|\Z)"
)
SQL_KEYWORDS = re.compile(
    r"(?isx)\s*('[^']*'|\b(?:is|then|when|end|case|precision|integer|double|coalesce|null|not|int|boolean|text|decimal|and|or)\b|[0-9=>#/<+,\|\(\-\):]+|(\w+\W*\())\s*"
)


def _parse_column(name, calc):
    return {
        "name": name,
        "calc": calc.strip(),
        "uses": list(set(SQL_KEYWORDS.sub(" ", calc.strip()).split())),
    }


def _get_columns(query):
    select = SELECT_RGX.search(query)[1]
    index = 0
    answer = []
    while m := COLUMN.search(select, index):
        full, calc, name = [m[n] for n in range(3)]
        if "(" in full and not (fn.extract_brackets(full, 0)):
            x = fn.extract_brackets(select, index)
            m = COLUMN.search(select.replace(x, PLACE_HOLDER), index)
            full, calc, name = [m[n].replace(PLACE_HOLDER, x) for n in range(3)]

        index = m.start() + len(full)
        answer.append(_parse_column(name, calc))
    return answer


# def check_calc_brackets(columns):


def _get_all_table_referenced(select):
    x = [{"name": k, "alias": v} for k, v in TABLE_NAME_RGX.findall(select) if k]
    return x or None


def _collect_parts(query):
    i = 0
    parts = {}
    while x := CTE_RGX.search(query, i):
        cte_name = x[1]
        body = fn.extract_brackets(query, x.end())
        parts[cte_name] = body.strip()[:-1][1:]
        i = len(body) + x.end()
    parts["main_select"] = SELECT_RGX.search(query, i)[0]
    return parts


def get_query_parts(sql_file):
    file = Path(sql_file).read_text()
    if not VIEW_RGX.search(file):
        return JsonQ()

    type, view, query = VIEW_RGX.findall(file)[0]
    parts = [
        {
            "name": k,
            "columns": _get_columns(v),
            "referenced_table": _get_all_table_referenced(v),
        }
        for k, v in _collect_parts(query).items()
    ]
    return JsonQ(
        {
            "type": (type or "view").lower(),
            "view": view,
            "sql": {"query": query, "parts": parts},
        }
    )
