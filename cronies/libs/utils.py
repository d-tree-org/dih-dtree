import json, collections, re
import secrets
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from typing import Callable, Any
from subprocess import Popen, PIPE
from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime import datetime
from collections import namedtuple
import numpy as np
import asyncio, aiohttp


class _Command:
    def __init__(self, cmd, bg=True):
        self.cmd = cmd.split(" ")
        self.bg = bg
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.shell = Popen(self.cmd, stdout=PIPE, stderr=PIPE)
        self.results = ""

    def _io_once(self):
        x = "readline" if self.bg else "read"
        self.results = getattr(self.shell.stdout, x)().decode()
        return self

    def _io_poll(self):
        while self.shell.poll() is None:
            print(self.shell.stderr.readline().decode())
        return self.__exit__()

    def __enter__(self):
        f1 = self.executor.submit(self._io_once)
        f2 = self.executor.submit(self._io_poll)
        f1.result()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.shell.kill()
        self.executor.shutdown()


def run_cmd(cmd, bg=True):
    return _Command(cmd, bg)


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

async def default_consumer_func(index,result):
    pass

async def do_chunks_async(
    source: list,
    chunk_size: int,
    func: "Callable[..., Awaitable[Any]]",  # func needs to be an async function
    consumer_func: "Callable[..., Awaitable[None]]" = default_consumer_func,  # Assuming print for simplicity
):
    chunks = [source[i : i + chunk_size] for i in range(0, len(source), chunk_size)]
    tasks = [func(chunk) for chunk in chunks]

    for i, task in enumerate(asyncio.as_completed(tasks)):
        r = await task
        await consumer_func(i, r)


def get_config(config_file="/dih/common/configs/${proj}.json"):
    with open(config_file) as file:
        x = json.load(file)
        c = x["cronies"]
        c["tunnel_ssh"] = c.get(
            "tunnel_ssh", "echo running sql without opening ssh-tunnel"
        )
        for k, v in x.items():
            if isinstance(v, (str, int, float)):
                c[k] = x[k]
    return namedtuple("p", c.keys())(*c.values())


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


def file_text(file_name):
    with open(file_name) as file:
        return file.read()


def to_file(file_name, text, mode="w"):
    with open(file_name, mode=mode) as file:
        return file.write(text)


def parse_month(date: str):
    formats = ["%Y%m", "%Y%m%d", "%d%m%Y", "%m%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(re.sub(r"\W+", "", date), fmt)
            return dt.replace(day=1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("Invalid date format")


def walk(element, action):
    if isinstance(element, dict):
        parent = {key: walk(value, action) for key, value in element.items()}
        return action(parent)
    elif isinstance(element, list):
        return [walk(item, action) for item in element]
    else:
        return action(element)


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
        json_payload = json.dumps(payload, cls=NumpyEncoder)
        try:
            async with session.post(
                url, data=json_payload, headers={"Content-Type": "application/json"}
            ) as response:
                if response.status in (200, 201):
                    return await response.json()  # Parse JSON content
                else:
                    error_message = await response.text()  # Get error message
                    raise Exception(f"Error {response.status}: {error_message}")
        except aiohttp.ClientError as e:
            raise Exception(f"Request failed: {e}")
