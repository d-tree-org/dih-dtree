from sqlalchemy import create_engine, text
import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re
from collections import namedtuple
import dihlibs.functions as fn
from pathlib import Path
from dihlibs.dhis.configuration import Configuration


class DB:
    def __init__(self, postgres_url="", ssh_command=None, conf: Configuration = None):
        self.connection_string = postgres_url
        self.ssh_command = ssh_command

        if isinstance(conf, Configuration):
            self.ssh_command = conf.get("tunnel_ssh")
            self.connection_string = conf.get("postgres_url")

        self.engine = create_engine(self.connection_string)
        self.Session = sessionmaker(bind=self.engine)

    def open_ssh(self,key_file):
        cmd=self.ssh_command + f" -i {key_file}";
        print(cmd)
        return fn.run_cmd(cmd)

    def exec(self, query, params=None):
        with self.Session() as session:
            try:
                session.execute(text(query), params)
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Error executing query: {e}")

    def query(self, query, params=None):
        return pd.read_sql_query(text(query), self.engine, params=params)

    def file(self, filename, params=None):
        with open(filename, "r") as file:
            return self.query(file.read(), params)

    def tables(self, schema="public"):
        query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"
        return self.query(query)

    def views(self, schema="public"):
        query = f"SELECT table_name FROM information_schema.views WHERE table_schema = '{schema}'"
        return self.query(query)

    def table(self, table_name, schema="public"):
        # sql_file=Path(__file__).parent / "describe_table.sql"
        sql_file = pkg_resources.resource_filename("dihlibs", "data/describe_table.sql")
        return self.file(sql_file, {"table": table_name, "schema": schema})

    def view(self, view_name):
        return self.query(
            "SELECT definition FROM pg_views WHERE viewname = '{view_name}'"
        )

    def select_part_matview(self, sql_file):
        with open(sql_file, "r") as file:
            (sql,) = re.findall(
                r"create mater[^\(]*\(([^;]+)\)",
                file.read(),
                re.MULTILINE | re.IGNORECASE,
            )
            return sql
