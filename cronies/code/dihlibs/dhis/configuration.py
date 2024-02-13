import os, sys
import pandas as pd
import sqlalchemy
import requests, asyncio
from functools import partial
import argparse

from dihlibs.dhis import DHIS, UploadSummary
from dihlibs.db import DB
from dihlibs import functions as fn
from dihlibs import cron_logger as logger
from dihlibs import drive as gd


class Configuration:
    def __init__(self):
        args = self._get_commandline_args()
        self._decrypt_config(args)
        self.conf = self._load(args)

    def _decrypt_config(self, args):
        file = args["config-file"]
        folder = file.replace(".zip.enc", "")
        zipped = file.replace(".enc", "")
        command = f" rm -rf {folder} {zipped} && decrypt {file} "#&& unzip {zipped}" #unzip is now a part of decrypt definition

        with fn.run_cmd(command) as cmd:
            cmd.wait()
            cmd.send(fn.file_text(".env"))
            while (x := cmd.wait()) is not None:
                print(x)
        print("nje ya command")

    def _load(self, args):
        folder = args.get("config-file").replace(".zip.enc", "")
        x = fn.file_dict(f"{folder}/config.yaml")
        c = x["cronies"]
        c["country"] = x["country"]
        c["ssh"] = c.get("tunnel_ssh", "echo No ssh command") + f" -i {folder}/tunnel"
        c["month"] = fn.parse_month(args.get("month", fn.get_month(-1)))
        c["selection"] = args.get("selection")
        c["task_dir"] = os.path.basename(os.getcwd())
        c["config-file"] = args.get("config-file")
        c["config-folder"] = args.get("config-file").replace(".zip.enc", "")
        c.update(self._get_mappings(c))
        return c

    def _get_commandline_args(self):
        parser = argparse.ArgumentParser(
            description="For moving data from postgresql warehouse to dhis2"
        )
        parser.add_argument("-m", "--month", type=str, help="Date in format YYYY-MM")
        parser.add_argument("-s", "--selection", type=str, help="Element Selection")
        parser.add_argument(
            "config-file",
            nargs="?",
            default="secret.zip.enc",
            help="Configuration File path",
        )
        parser.add_argument("-d", "--deploy", type=str, help="Deploys a cron")
        args = vars(parser.parse_args())  # Convert args to dictionary
        return {k: v for k, v in args.items() if v is not None}

    def _get_mappings(self, conf):
        log = logger.get_logger_task(conf.get("task_dir"))
        log.info("seeking mapping file from google drive ....")
        drive = gd.Drive(fn.file_dict(f"{conf.get('config-folder')}/google.json"))
        excel = drive.get_excel(conf.get("data_element_mapping"))

        emap = pd.read_excel(excel, "data_elements")
        emap.dropna(subset=["db_column", "element_id"], inplace=True)
        emap["map_key"] = emap.db_view + "_" + emap.db_column
        emap = emap.set_index("map_key")
        emap = self._apply_element_selection(conf, emap)
        return {"mapping_excel": excel, "mapping_element": emap}

    def _apply_element_selection(self, conf: dict, emap: pd.DataFrame):
        selection = conf.get("selection")
        if selection:
            return emap[(emap.selection.isin(selection.strip().split(" ")))]
        else:
            return emap[
                ~emap.selection.isin(["skip", "deleted", "deprecated", "false"])
            ]

    def get(self, what: str):
        return self.conf.get(what)

    def clear_stuff(self):
        file = self.conf["config-file"]
        folder = file.replace(".zip.enc", "")
        zipped = file.replace(".enc", "")
        command = f" rm -rf {folder} {zipped} "
        with fn.run_cmd(command) as cmd:
            print(cmd.wait())
