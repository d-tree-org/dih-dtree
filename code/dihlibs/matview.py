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
INDEX_RGX = re.compile(
    r"(?isx)create\s+(unique\s+)?index\s+(?:if\s+not\s+exists\s+)?(\w+)\s+on\s+(\w+)\s*(?:using\s+(\w+))?\s*\(([^)]+)\)"
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


def _get_indexes(file_content):
    """Extract all index definitions from the SQL file."""
    indexes = []
    for match in INDEX_RGX.finditer(file_content):
        is_unique = bool(match.group(1))
        index_name = match.group(2)
        table_name = match.group(3)
        method = match.group(4) or "btree"
        columns_str = match.group(5)
        # Parse column names from the index definition
        columns = [c.strip() for c in columns_str.split(",")]
        indexes.append({
            "name": index_name,
            "table": table_name,
            "unique": is_unique,
            "method": method.lower(),
            "columns": columns,
        })
    return indexes


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
    indexes = _get_indexes(file)
    return JsonQ(
        {
            "type": (type or "view").lower(),
            "view": view,
            "sql": {"query": query, "parts": parts},
            "indexes": indexes,
        }
    )


def _strip_prefix(name):
    """Remove table prefix from column name (e.g., 't.col' -> 'col')."""
    return name.split('.')[-1] if name and '.' in name else name


def remove_comments(sql):
    """Remove SQL comments (-- and /* */) from query."""
    sql = re.sub(r'--[^\n]*', '', sql)
    return re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)


def get_group_by_columns(query):
    """Extract GROUP BY column names from a query."""
    query = remove_comments(query)
    m = re.search(r'GROUP\s+BY\s+([^;]+?)(?:ORDER|HAVING|LIMIT|\)|;|\Z)', query, re.I | re.DOTALL)
    if not m:
        return None
    return [
        _strip_prefix(c.strip()).split()[0]
        for c in m.group(1).split(',')
        if c.strip() and '(' not in c and "'" not in c
    ]


def build_alias_map(referenced_tables):
    """Build map of table_alias -> view_name from referenced tables.

    Args:
        referenced_tables: List from _get_all_table_referenced()

    Returns:
        dict: {alias: view_name, view_name: view_name}
    """
    alias_map = {}
    for ref in referenced_tables or []:
        name = ref.get('name', '')
        if name:
            alias_map[ref.get('alias', name)] = name
            alias_map[name] = name
    return alias_map


def get_cte_columns(jq):
    """Extract columns defined in each CTE/part of a query.

    Args:
        jq: JsonQ from get_query_parts()

    Returns:
        dict: {cte_name: {column_names}}
    """
    cte_cols = {}
    for part in jq.get('..parts[*]').val() or []:
        pj = JsonQ.from_object(part)
        names = pj.get('columns[*].name').val() or []
        if isinstance(names, str):
            names = [names]
        cte_cols[pj.str('name')] = {_strip_prefix(n) for n in names if n}
    return cte_cols


def iter_views(folder):
    """Iterate over all valid views in a folder.

    Args:
        folder: Path to folder containing SQL files

    Yields:
        tuple: (file_path, JsonQ) for each valid view
    """
    for file in glob(f"{folder}/*sql") + glob(f"{folder}/**/*sql"):
        jq = get_query_parts(file)
        if not jq.is_empty():
            yield file, jq


RESERVED_WORDS = {
    'select', 'from', 'where', 'join', 'left', 'right', 'inner', 'outer', 'on',
    'and', 'or', 'not', 'null', 'true', 'false', 'as', 'in', 'is', 'like',
    'between', 'case', 'when', 'then', 'else', 'end', 'order', 'by', 'group',
    'having', 'limit', 'offset', 'union', 'all', 'distinct', 'insert', 'update',
    'delete', 'create', 'drop', 'alter', 'table', 'index', 'view', 'primary',
    'key', 'foreign', 'references', 'default', 'constraint', 'check', 'unique',
    'values', 'into', 'set', 'user', 'date', 'time', 'timestamp', 'interval',
    'year', 'month', 'day', 'hour', 'minute', 'second', 'current', 'row',
    'rows', 'over', 'partition', 'window', 'range'
}


def build_view_registry(folder):
    """Build a registry of all views and their columns.

    Args:
        folder: Path to folder containing SQL files

    Returns:
        dict: {view_name: {'file': path, 'columns': {col_names}}}
    """
    registry = {}
    for file in glob(f"{folder}/*sql") + glob(f"{folder}/**/*sql"):
        jq = get_query_parts(file)
        if jq.is_empty():
            continue
        view_name = jq.str('view')
        if not view_name:
            continue
        names = jq.get('..columns[*].name').val() or []
        if isinstance(names, str):
            names = [names]
        registry[view_name] = {
            'file': file,
            'columns': {_strip_prefix(n) for n in names if n}
        }
    return registry
