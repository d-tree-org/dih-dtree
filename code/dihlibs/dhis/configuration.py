import os, sys, re, json
import pandas as pd
import sqlalchemy
import requests, asyncio
from functools import partial
import argparse

from dihlibs.dhis import DHIS, UploadSummary
from dihlibs import functions as fn
from dihlibs import cron_logger as logger
from dihlibs import drive as gd
import pkg_resources as pkr
import shlex, shutil, tempfile, yaml


class Configuration:
    def __init__(self):
        self.conf = self._load()
        action = self.get("action")
        if action is None:
            self.conf.update(self._get_mappings(self.conf))
            return

        elif action == "dhis":
            self.create_dhis_compose()
            exit(0)

        elif action == "cron":
            self.create_cron_compose()
            exit(0)

        else:
            try:
                data = fn.read_non_blocking([sys.stdin.fileno(), sys.stderr.fileno()])
                data_input = f"<<<{shlex.quote(data)}" if data else ""
                command = f"perform {action} {self.get('config-file')} {data_input}"
                fn.cmd_wait(command,verbose=True)
            except KeyboardInterrupt:
                pass
            exit(0)

    def _load(self):
        args = self._get_commandline_args()
        if args.get("action"):
            return args

        file = args.get("config-file")
        folder = file.replace(".zip.enc", "")
        self.conf = args
        conf = self._get_conf(args)
        c = conf["cronies"]
        c["action"] = args.get("action")
        c["country"] = conf["country"]
        # c["ssh"] = c.get("tunnel_ssh", "echo No ssh command")
        c["month"] = fn.parse_month(args.get("month", fn.get_month(-1)))
        c["selection"] = args.get("selection")
        c["task_dir"] = os.path.basename(os.getcwd())
        c["config-file"] = args.get("config-file")
        c["config-folder"] = args.get("config-file").replace(".zip.enc", "")
        return c

    def pick_config_file(self, args):
        if args.get("config-file") is None:
            file = next(filter(lambda x: "zip.enc" in x, os.listdir()), "no-file")
        else:
            file = args.get("config-file")
        return file

    def _get_commandline_args(self):
        parser = argparse.ArgumentParser(
            description="For moving data from postgresql warehouse to dhis2"
        )
        parser.add_argument("-m", "--month", type=str, help="Date in format YYYY-MM")
        parser.add_argument("-s", "--selection", type=str, help="Element Selection")
        parser.add_argument("-a", "--action", type=str, help="do various functions")
        parser.add_argument(
            "config-file",
            nargs="?",
            # default="secret.zip.enc",
            help="Configuration File path",
        )
        args = vars(parser.parse_args())  # Convert args to dictionary
        args["config-file"] = self.pick_config_file(args)
        args["config-folder"] = args.get("config-file").replace(".zip.enc", "")
        return {k: v for k, v in args.items() if v is not None}

    def _get_mappings(self, conf):
        log = logger.get_logger_task(conf.get("task_dir"))
        log.info("seeking mapping file from google drive ....")
        drive = gd.Drive(json.loads(self.get_file("google.json")))
        excel = drive.get_excel(conf.get("data_element_mapping"))

        emap = pd.read_excel(excel, "data_elements")
        emap.dropna(subset=["db_column", "element_id"], inplace=True)
        emap["map_key"] = emap.db_view + "_" + emap.db_column
        emap = emap.set_index("map_key")
        emap = self._apply_element_selection(conf, emap)
        return {"mapping_excel": excel, "mapping_element": emap}

    def _apply_element_selection(self, conf: dict, emap: pd.DataFrame):
        to_skip = ["skip", "deleted", "deprecated", "false", "ruka", "ficha"]
        selection = conf.get("selection")
        if selection:
            return emap[(emap.selection.isin(selection.strip().split(" ")))]
        else:
            return emap[~emap.selection.isin(to_skip)]

    def get(self, what: str, default=None):
        return self.conf.get(what, default)

    def _get_conf(self, args):
        file = args.get("config-file")
        folder = file.replace(".zip.enc", "")
        if os.path.isdir(folder):
            conf = fn.file_dict(f"{folder}/config.yaml")
            if args.get("action") != "encrypt":
                command = f" strong_password 64 > .env && encrypt {folder} < .env "
                print(fn.cmd_wait(command))
                args["config-file"] = f"{file}.zip.enc"
                conf["config-file"] = f"{file}.zip.enc"
            return conf
        else:
            return yaml.safe_load(self.get_file("config.yaml"))

    def get_backend_conf(self):
        args = self._get_commandline_args()
        dih_conf = self._get_conf(args)
        conf = fn.get(dih_conf, "backends.dhis")
        conf.update(
            {
                "proj": self.get("config-folder"),
                "user": dih_conf.get("dih_user"),
                "dih_user": dih_conf.get("dih_user"),
                "env_file": f'compose/{self.get("config-folder")}.env',
            }
        )
        return {k.strip(): v.strip() for k, v in conf.items()}

    def create_cron_compose(self):
        os.makedirs(".cache/docker/cronies", exist_ok=True)
        cronies = pkr.resource_filename("dihlibs", "data/docker/cronies.zip")

        command = f"cd .cache/docker && cp {cronies} . && unzip -o cronies.zip -d . && rm cronies.zip "
        fn.cmd_wait(command)
        fn.to_file(".cache/docker/cronies/.env", f'proj={self.get("config-folder")}')
        fn.cmd_wait("turn_on_cron_container",verbose=True)

    def create_dhis_compose(self):
        os.makedirs(".cache/docker/backend", exist_ok=True)
        print('changes hapa')
        # create compose file
        backend = pkr.resource_filename("dihlibs", "data/docker/backend.zip")
        command = f"cd .cache/docker && cp {backend}  . && unzip -o backend.zip -d . && rm backend.zip "
        fn.cmd_wait(command)
        comp = fn.file_text(f".cache/docker/backend/dhis/compose/compose-template.yml")
        conf = self.get_backend_conf()
        for key, value in conf.items():
            comp = comp.replace(f"${{{key}}}", value)
        fn.to_file(f".cache/docker/backend/dhis/{conf.get('proj')}-compose.yml", comp)
        # create env file
        entries = [f"{k}={v}" for k, v in conf.items()]
        fn.lines_to_file(f'.cache/docker/backend/dhis/{conf.get("env_file")}', entries)
        #turn on containers right away
        command=f'turn_on_dhis_containers {conf.get("proj")}'
        fn.cmd_wait(command,verbose=True)

    def get_file(self, filename):
        file = self.get("config-file")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = os.path.join(temp_dir, file)
            shutil.copy(file, temp)
            password = shlex.quote(fn.file_text(".env"))
            print(fn.cmd_wait(f"cd {temp_dir} && decrypt {temp} <<<{password}"))
            return fn.file_text(temp.replace(".zip.enc", "/" + filename))
