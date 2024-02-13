from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from typing import Callable, Any
from subprocess import Popen, PIPE
import select,os
from pathlib import Path


class _Command:
    def __init__(self, cmd, bg=True):
        bash_functions=Path(__file__).parent / "bash/script.sh"
        self.cmd = f'. {bash_functions} && {cmd.strip()}'
        self.bg = bg
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.shell = Popen(self.cmd, stdin=PIPE,stdout=PIPE, stderr=PIPE, shell=True, executable="/bin/bash")


    def interract(self, max_bytes=1024):
        while self.shell.poll() is None:
            readables = [self.shell.stdout.fileno(), self.shell.stderr.fileno()]
            ready_to_read, _, _ = select.select(readables, [], [], 0)
            data=[]
            for fd in ready_to_read:
                data.append(os.read(fd, max_bytes).decode().strip())
            data=[x for x in data if x]
            if len(data)>0:
                return '\n'.join(data)

    def __enter__(self):
        return self


    def wait(self):
        f2 = self.executor.submit(self.interract)
        return f2.result()

    def send(self,msg):
        self.shell.stdin.write(msg.encode() + b'\n')
        self.shell.stdin.flush()

    def __exit__(self, exc_type, exc_value, traceback):
        self.shell.kill()
        self.executor.shutdown()


