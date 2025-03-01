import time, re, json
from base64 import b64encode
import secrets
import concurrent.futures
from typing import List,Callable,Awaitable, Any
from datetime import datetime,timezone
from dateutil.relativedelta import relativedelta
from collections import namedtuple
import numpy as np
import asyncio, aiohttp, yaml, string, os, hashlib, select
from dihlibs.command import _Command
from collections import deque
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
import jwt
import pandas as pd
from dihlibs.fs_secret import encrypt_secret,decrypt_secret

DEFAULT_TIMEZONE=tz=timezone(timedelta(hours=3))


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
    source: List[Any],
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
    source: List[Any], 
    chunk_size: int, 
    func: Callable[[Any], Awaitable[Any]], 
    consumer_func: Callable[[int, Any], Awaitable[None]] = default_consumer_func,  # default consumer function
    max_concurrency: int = 10  # limit for concurrent tasks
):
    semaphore = asyncio.Semaphore(max_concurrency)  # limit concurrent tasks

    async def limited_func(item):
        async with semaphore:
            return await func(item)

    chunks = [source[i : i + chunk_size] for i in range(0, len(source), chunk_size)]
    
    for chunk in chunks:
        tasks = [asyncio.create_task(limited_func(item)) for item in chunk]
        for idx, result in enumerate(asyncio.as_completed(tasks)):
            try:
                res = await result
            except Exception as e:
                res = {"error": str(e)}
            await consumer_func(idx, res)



def is_binary(file_path):
    with open(file_path, "rb") as f:
        chunk = f.read(1024)  # Read a small part of the file
    return b"\x00" in chunk or any(byte > 127 for byte in chunk)

def file_dict(filename):
    with open(filename) as file:
        return json.load(file) if ".json" in filename else yaml.safe_load(file)

def load_secret_file(filename):
    secret=None
    if os.path.isfile(filename):
        if is_binary(filename):
            raise ValueError("File cannot be binary") 
        encrypt_secret (filename)
        secret = decrypt_secret(filename).decode('utf-8')
    else:
        secret = decrypt_secret(filename).decode('utf-8')
    if secret:
        return load_string_data(secret)

def load_string_data(data_str):
    try:
        return json.loads(data_str)  # Try JSON first
    except json.JSONDecodeError:
        try:
            return yaml.safe_load(data_str)  # Fall back to YAML
        except yaml.YAMLError:
            raise ValueError("Invalid JSON or YAML")

def load_file_data(file_name):
    _, ext = os.path.splitext(file_name)
    ext = ext.lower()
    text_loaders = {
        ".json": json.load,
        ".yaml": yaml.safe_load,
        ".yml": yaml.safe_load,
        ".jsonl": lambda f: [json.loads(line) for line in f],
    }
    # Loaders that use pandas directly
    pandas_loaders = {
        ".csv": pd.read_csv,
        ".xls": pd.read_excel,
        ".xlsx": pd.read_excel,
        ".ods": lambda f: pd.read_excel(f, engine="odf"),
        ".parquet": pd.read_parquet,
    }
    if ext in text_loaders:
        with open(file_name, "r", encoding="utf-8") as file:
            return text_loaders[ext](file)
    elif ext in pandas_loaders:
        return pandas_loaders[ext](file_name).to_dict(orient="records")
    else:
        supported = ", ".join(list(text_loaders.keys()) + list(pandas_loaders.keys()))
        error = f"Unsupported file extension '{ext}'. Supported: {supported}"
        raise ValueError(error)


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


def get_month(delta,tz=DEFAULT_TIMEZONE):
    sign = 1 if delta > 0 else -1
    x = datetime.now(tz) + sign * relativedelta(months=abs(delta))
    return x.replace(day=1).strftime("%Y-%m-01")


def days_delta(delta,tz=DEFAULT_TIMEZONE):
    sign = 1 if delta > 0 else -1
    x = datetime.now(tz) + sign * relativedelta(days=abs(delta))
    return x.strftime(r"%Y-%m-%d")


def file_binary(file_name):
    with open(file_name, "rb") as file:
        return file.read()


def text(filename, text=None, mode="w"):
    if text is None:
        with open(filename, mode="r") as file:
            return file.read()
    with open(filename, mode) as file:
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


def to_snake_case(s):
    return re.sub(r"([a-z0-9])([A-Z])|[\s_-]+", r"\1_\2", s).lower()


def is_recent_file(filename, age=3600 * 24):
    return (
        os.path.isfile(filename)
        and time.time() - os.path.getctime(filename) < age
        and os.path.getsize(filename) > 2
    )


def _core_cache_decorator(func):
    def wrapper(cached, *args, **kwargs):
        # Core caching logic
        if is_recent_file(cached):
            print(cached, "exists, not downloading")
            data = text(cached)
            return json.loads(data) if ".json" in cached else data
        else:
            print(cached, "downloading")
            result = func(cached,*args, **kwargs)
            if result is not None:
                os.makedirs(".cache", exist_ok=True)
                text(cached, json.dumps(result) if ".json" in cached else result)
            return result
    return wrapper

def cache_method_decorator(func):
    @_core_cache_decorator
    def wrapper(self, filename, *args, **kwargs):
        cached = f".cache/{filename}.json" if "." not in filename else filename
        return func(self, cached, *args, **kwargs)
    return wrapper


def cache_decorator(func):
    return cache_method_decorator(func)


def cache_function_decorator(func):
    @_core_cache_decorator
    def wrapper(filename, *args, **kwargs):
        cached = f".cache/{filename}.json" if "." not in filename else filename
        return func(cached, *args, **kwargs)
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

def now(tz=DEFAULT_TIMEZONE):
    return datetime.now(tz)

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
    if isinstance(ms, str):
        ms = int(ms)
    if ms:
        return datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")


def fuzzy_match(left_df, right_df, left_keys=[], right_keys=[], method="0"):
    lkey = ",".join(left_keys)
    left_df.loc[:, lkey] = (
        left_df[left_keys].fillna("").apply(lambda row: ",".join(row.values), axis=1)
    )
    rkey = ",".join(right_keys)
    right_df.loc[:, rkey] = (
        right_df[right_keys].fillna("").apply(lambda row: ",".join(row.values), axis=1)
    )

    methods = [
        fuzz.token_set_ratio,
        fuzz.token_sort_ratio,
        fuzz.partial_token_set_ratio,
        fuzz.partial_token_sort_ratio,
        fuzz.ratio,
    ]
    match = left_df[lkey].apply(
        lambda x: right_df[rkey].apply(lambda y: methods[int(method)](x, y))
    )
    left_df["match"] = match.max(axis=1)

    rcolumns = right_df.columns.map(lambda r: "r:" + r)
    left_df[rcolumns] = right_df.loc[match.idxmax(axis=1)].values
    left_df.loc[left_df[lkey].isna(), rcolumns] = ""

    return (
        left_df.sort_values("match", ascending=False)
        .drop(columns=["r:" + rkey, lkey])
        .reset_index(drop=True)
    )


def uuid_from_hash(input_string):
    if not isinstance(input_string, str):
        raise ValueError("Input must be a string")
    hash = hashlib.sha256(input_string.encode()).hexdigest()
    hash = hash[:12] + "4" + hash[13:]
    variant_char = (int(hash[16], 16) & 0x3) | 0x8
    hash = hash[:16] + format(variant_char, "x") + hash[17:]
    uuid = f"{hash[:8]}-{hash[8:12]}-{hash[12:16]}-{hash[16:20]}-{hash[20:32]}"
    return uuid


def flattern_jsonb(df_column,sep='.'):
    _flattern = lambda s:flattern(s,sep)
    return df_column.map(json.loads).map(_flattern).tolist()


def is_null(*args):
    is_nan = lambda x: (
        np.isnan(x) or np.isinf(x) if isinstance(x, (float, int)) else False
    )
    return any(x is None or is_nan(x) for x in args)


def no_null(*args):
    return not is_null(*args)

def coalesce(*args):
    return next((x for x in args if no_null(x)), None)

def generate_dates(start_date, end_date, interval_type="months", interval_value=1):
    # Parse the input dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    # Create a list to store the intervals
    intervals = []
    # Define a dictionary to map interval types to their corresponding functions
    interval_mapping = {
        "days": lambda date, value: date + timedelta(days=value),
        "weeks": lambda date, value: date + timedelta(weeks=value),
        "months": lambda date, value: date + relativedelta(months=value),
        "years": lambda date, value: date + relativedelta(years=value),
    }
    # Ensure the interval type is valid
    while start <= end:
        # Format the date as YYYYMMDD
        interval_str = start.strftime("%Y-%m-%d")
        intervals.append(interval_str)
        # Increment the start date using the appropriate function
        start = interval_mapping[interval_type](start, interval_value)
    return intervals


def generate_token(secret_key,lifespan_mins,tz=DEFAULT_TIMEZONE):
    return jwt.encode(
        {"exp": datetime.now(tz) + timedelta(minutes=lifespan_mins)},
        secret_key,
        algorithm="HS256",
    )

def has_expired_client_side(access_token,tz=DEFAULT_TIMEZONE):
    try:
        payload = jwt.decode(access_token, options={"verify_signature": False})
        exp_timestamp = payload.get("exp", 0)
        exp_time=datetime.fromtimestamp(exp_timestamp,tz=tz)
        return exp_time < datetime.now(tz=tz)
    except jwt.DecodeError:
        return True  

def has_expired(token,secret_key,lifespan_mins=10,tz=DEFAULT_TIMEZONE):
    try:
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        remaining_time = datetime.fromtimestamp(decoded["exp"], tz) - datetime.now(tz)
        return remaining_time < timedelta(minutes=lifespan_mins * 0.05) 
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def refresh_token(token,secret_key,lifespan_mins=5,tz=DEFAULT_TIMEZONE):
    still_active=has_expired(token,secret_key,lifespan_mins,tz)
    return token if still_active else generate_token(secret_key,tz) if still_active is False else None

def basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
    return f'Basic {token}'
