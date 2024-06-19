import json, re
import time
import secrets
import concurrent.futures
from typing import Callable, Any
from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import namedtuple
import numpy as np
import asyncio, aiohttp
import yaml
import string
import os
import select
from dihlibs.command import _Command
from collections import deque
from fuzzywuzzy import fuzz


DONE = object()

def run_cmd(cmd, bg=True):
    return _Command(cmd, bg)


def cmd_wait(cmd, bg=True, verbose=False):
    with _Command(cmd, bg) as proc:
        rs = []
        while (x := proc.wait()) is not None:
            if verbose:
                print(x)
            rs.append(x)
        return "\n".join(rs)


def do_chunks(
    source: list,
    chunk_size: int,
    func: Callable[..., Any],
    consumer_func: Callable[..., None] = print,
    thread_count: int = 5,
):
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as ex:
        chunks = [source[i : i + chunk_size] for i in range(0, len(source), chunk_size)]
        tasks = [ex.submit(func, chunk) for chunk in chunks]
        for i, res in enumerate(concurrent.futures.as_completed(tasks)):
            r = res.result()
            consumer_func(i, r)


async def default_consumer_func(index, result):
    pass


async def do_chunks_async(
    source: list,
    chunk_size: int,
    func: "Callable[..., Awaitable[Any]]",
    consumer_func: "Callable[..., Awaitable[None]]" = default_consumer_func,  # Assuming print for simplicity
):
    chunks = [source[i : i + chunk_size] for i in range(0, len(source), chunk_size)]
    for chunk in chunks:
        tasks = [asyncio.create_task(func(item)) for item in chunk]
        for idx, result in enumerate(asyncio.as_completed(tasks)):
            await consumer_func(idx, await result)


def file_dict(filename):
    with open(filename) as file:
        return json.load(file) if ".json" in filename else yaml.safe_load(file)


def get_config(config_file="/dih/common/configs/${proj}.json"):
    x = file_dict(config_file)
    c = x["cronies"]
    c["country"] = x["country"]
    c["tunnel_ssh"] = c.get("tunnel_ssh", "echo not opening ssh-tunnel")
    return c

def to_namedtuple(obj: dict):
    def change(item):
        if isinstance(item, dict):
            NamedTupleType = namedtuple("NamedTupleType", item.keys())
            return NamedTupleType(**item)
        return item

    return walk(obj, change)

def get_month(delta):
    ve = 1 if delta > 0 else -1
    x = datetime.today() + ve * relativedelta(months=abs(delta))
    return x.replace(day=1).strftime("%Y-%m-01")
    
def days_delta(delta):
    ve = 1 if delta > 0 else -1
    x = datetime.today() + ve * relativedelta(days=abs(delta))
    return x.strftime(r"%Y-%m-%d")

def file_binary(file_name):
    with open(file_name, "rb") as file:
        return file.read()

def text(filename,text=None,mode='w'):
    if text is None:
        with open(filename,mode='r') as file:
            return file.read() 
    with open(filename,mode) as file:
        file.write(text)


def lines_to_file(file_name, lines: list, mode="w"):
    data = "\n".join(lines)
    text(file_name, data)

def parse_month(date: str):
    formats = ["%Y%m", "%Y%m%d", "%d%m%Y", "%m%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(re.sub(r"\W+", "", date), fmt)
            return dt.replace(day=1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("Invalid date format")


def parse_date(date: str):
    formats = ["%Y-%m-%d", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%m-%d-%Y"]
    date = "-".join(y.zfill(2) for y in re.split(r"\W+", date))
    for fmt in formats:
        try:
            dt = datetime.strptime(date, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("Invalid date format")


def strong_password(length=16):
    if length < 12:
        raise ValueError(
            "Password length should be at least 12 characters for security"
        )
    characters = string.ascii_letters + string.digits + string.punctuation
    password = "".join(secrets.choice(characters) for _ in range(length))
    return password


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super().default(obj)


async def post(url, payload):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                data=json.dumps(payload, cls=NumpyEncoder),
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status in (200, 201):
                    return await response.json()  # Parse JSON content
                else:
                    return {"status": "error", "error": await response.text()}
        except aiohttp.ClientError as e:
            return {"status": "error", "error": f"Request failed: {e}"}


def read_non_blocking(readables: list):
    max_bytes = 1024
    ready_to_read, _, _ = select.select(readables, [], [], 0)
    data = []
    for fd in ready_to_read:
        data.append(os.read(fd, max_bytes).decode("utf-8", errors="ignore").strip())
    data = [x for x in data if x]
    if len(data) > 0:
        return "\n".join(data)


def flattern(item, sep="_"):
    queue = deque([("", item)])
    flat = {}
    while queue:
        path, value = queue.popleft()
        if not isinstance(value, (list, dict)):
            flat[path.strip(sep)] = value
            continue

        iterable = value.items() if isinstance(value, dict) else enumerate(value)
        for k, v in iterable:
            queue.append((path + sep + str(k), v))
    return flat


def build_tree(nodes, get_parent_id=None):
    graph = {}
    for node in nodes:
        node.node_parent_id = get_parent_id(node)
        if node.node_parent_id not in graph:
            graph[node.node_parent_id] = []
        graph[node.node_parent_id].append(node)
    return graph


def bfs(graph, root, got_node):
    queue = deque([(root, [])])
    visited = set()
    results = []
    while queue:
        node, path = queue.popleft()
        if node.node_id in visited:
            continue
        elif (rs := got_node(path, node)) is DONE:
            return results
        elif rs is not None:
            results.append(rs)

        visited.add(node.node_id)
        for child in graph.get(node.node_id, []):
            queue.append((child, path + [node]))
    return results


def to_snake_case(s):
    return re.sub(r"([a-z0-9])([A-Z])|[\s_-]+", r"\1_\2", s).lower()


def is_recent_file(filename, age=3600 * 24):
    return (
        os.path.isfile(filename)
        and time.time() - os.path.getctime(filename) < age
        and os.path.getsize(filename) > 2
    )


def cache_decorator(func):
    def wrapper(self, filename, age=3600, *args, **kwargs):
        cached = f".cache/{filename}.json" if "." not in filename else filename
        is_json = ".json" in cached
        if is_recent_file(cached):
            print(filename, "exists not downloading")
            data = text(cached)
            return json.loads(data) if is_json else data
        else:
            print(filename, f"downloading {filename}")
            result = func(self, filename, *args, **kwargs)
            if not re.match("^https?.*", filename) and result:
                print(cached)
                os.makedirs(".cache", exist_ok=True)
                text(cached, json.dumps(result) if is_json else result)
            return result

    return wrapper


def catch_json_error(func):
    # @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError:  # Catch JSON decoding errors
            response = func(*args, **kwargs)  # Get the original response
            return response.text  # Return the response text

    return wrapper


def walk(element, action):
    if isinstance(element, dict):
        gen = ((key, walk(value, action)) for key, value in element.items())
        parent = {key: value for key, value in gen if value is not None}
        return action(parent)
    elif isinstance(element, list):
        gen = (walk(item, action) for item in element)
        parent = [item for item in gen if item is not None]
        return action(parent)
    else:
        return action(element)


def get(_obj, field, defaultValue=None):
    """Retrieves a nested value with dot and array index support."""
    obj = _obj
    for part in field.split("."):
        try:
            obj = obj[part] if isinstance(obj, dict) else obj[int(part)]
        except (KeyError, IndexError, ValueError):
            return defaultValue
    return obj

def millisec_to_date(ms):
    if( isinstance(ms,str)):
        ms=int(ms)
    if ms:
        return datetime.fromtimestamp(ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

def fuzzy_match(left_df,right_df,left_keys=[],right_keys=[],method="0"):
    lkey=",".join(left_keys);
    left_df.loc[:,lkey]=left_df[left_keys].apply(lambda row:",".join(row.values),axis=1)
    rkey=",".join(right_keys);
    right_df.loc[:,rkey]=right_df[right_keys].apply(lambda row:",".join(row.values),axis=1)

    methods=[ fuzz.token_set_ratio ,fuzz.token_sort_ratio ,fuzz.partial_token_set_ratio ,fuzz.partial_token_sort_ratio,fuzz.ratio]
    match=left_df[lkey].apply(lambda x:right_df[rkey].apply(lambda y: methods[int(method)](x,y)))
    left_df['match']=match.max(axis=1)

    rcolumns=right_df.columns.map(lambda r:"r:"+r)
    left_df[rcolumns]=right_df.loc[match.idxmax(axis=1)].values
    left_df.loc[left_df[lkey].isna(),rcolumns]=''

    return left_df.sort_values('match',ascending=False).drop(columns=[rkey,lkey]).reset_index(drop=True)
