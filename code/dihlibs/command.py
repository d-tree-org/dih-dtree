from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from subprocess import Popen, PIPE
from pathlib import Path
import pkg_resources
import dihlibs.functions as fn



class _Command:
    def __init__(self, cmd, bg=True):
        bash_functions = pkg_resources.resource_filename('dihlibs', 'data/bash/script.sh')
        self.cmd = f'. $HOME/.bashrc && .  {bash_functions}  && {cmd.strip()}'
        self.bg = bg
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.shell = Popen(self.cmd, stdin=PIPE,stdout=PIPE, stderr=PIPE, shell=True, executable="/bin/bash")


    def interract(self):
        while self.shell.poll() is None:
            readables = [self.shell.stdout.fileno(), self.shell.stderr.fileno()]
            data=fn.read_non_blocking(readables)
            if data:
                return data;

    def __enter__(self):
        return self


    def wait(self,timeout=None):
        f2 = self.executor.submit(self.interract)
        try:
            return f2.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return 'command timed out';

    def send(self,msg):
        self.shell.stdin.write(msg.encode() + b'\n')
        self.shell.stdin.flush()

    def __exit__(self, exc_type, exc_value, traceback):
        self.shell.kill()
        self.executor.shutdown()

