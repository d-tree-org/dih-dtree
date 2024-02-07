from sqlalchemy import create_engine, text
import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re
from collections import namedtuple


class DB:
    def __init__(self, conf: namedtuple):
        self.connection_string = conf.postgres_url
        self.engine = create_engine(self.connection_string)
        self.Session = sessionmaker(bind=self.engine)

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
        return self.file("describe_table.sql", {"table": table_name, "schema": schema})

    def view(self, view_name):
        return self.query("SELECT definition FROM pg_views WHERE viewname = '{view_name}'")

    def select_part_matview(self,sql_file):
        with open(sql_file, "r") as file:
            (sql,) = re.findall(
                r"create mater[^\(]*\(([^;]+)\)",
                file.read(),
                re.MULTILINE | re.IGNORECASE,
            )
            return sql
