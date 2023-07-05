import logging

logging.basicConfig(level=logging.INFO)
message_logger = None
task_logger = None

def get_logger_message_only(logfile="../../logs/cron.log"):
    global message_logger
    if message_logger is None:
        message_logger = logging.getLogger("progress")
        message_logger.handlers = []
        message_logger.propagate = False

        formatter = logging.Formatter("%(message)s")

        # handler = logging.FileHandler(filename=logfile, delay=True)
        # handler.terminator = ""
        # handler.setLevel(logging.INFO)
        # message_logger.addHandler(handler)
        # handler.setFormatter(formatter)

        handler = logging.StreamHandler()
        handler.terminator = ""
        handler.setFormatter(formatter)
        message_logger.addHandler(handler)

    return message_logger


def get_logger_task(cron_name,logfile="../../logs/cron.log"):
    global task_logger
    formatter = logging.Formatter(
        f"%(message)s \033[38;5;22m({cron_name}:%(levelname)s:%(asctime)s)\033[0m",
        "%Y-%m-%d %H:%M:%S",
    )
    if task_logger is None:
        task_logger = logging.getLogger("task")
        task_logger.handlers = []
        task_logger.propagate = False

        # handler = logging.FileHandler(filename=logfile)
        # handler.setLevel(logging.INFO)
        # handler.setFormatter(formatter)
        # task_logger.addHandler(handler)

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        task_logger.addHandler(handler)
    return task_logger