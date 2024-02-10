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
import asyncio, aiohttp, requests
import argparse
import yaml
import string
import os
import select
from dihlibs.command import _Command



def run_cmd(cmd, bg=True):
    return _Command(cmd, bg)


def get(obj, field, defaultValue=None):
    """Retrieves a nested value with dot and array index support."""
    for part in field.split("."):
        try:
            obj = obj[part] if isinstance(obj, dict) else obj[int(part)]
        except (KeyError, IndexError, ValueError):
            return defaultValue
    return obj


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
        gen = ((key, walk(value, action)) for key, value in element.items())
        parent = {key: value for key, value in gen if value is not None}
        return action(parent)
    elif isinstance(element, list):
        gen = (walk(item, action) for item in element)
        parent = [item for item in gen if item is not None]
        return action(parent)
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

