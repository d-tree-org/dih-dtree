import json, collections, logging
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from typing import Callable, Any
from subprocess import Popen, PIPE
from datetime import datetime
from dateutil.relativedelta import relativedelta

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


def get_config(config_file="/dih/common/configs/${proj}.json"):
    with open(config_file) as file:
        x = json.load(file)
        c = x['cronies']
        for k,v in x.items():
            if isinstance(v, (str, int, float)):
                c[k] = x[k]
    return collections.namedtuple("p", c.keys())(*c.values())


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


def log_response(rs, dot=None):
    if dot and rs.response_code == 200 or rs.response_code == 201:
        print(".", end="", flush=True)
    else:
        print(rs.text)
    return rs.json().get("status")

