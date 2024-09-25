from sqlalchemy import create_engine, text
import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re,os
import dihlibs.functions as fn
from pathlib import Path
import pkg_resources as pkg
from dihlibs.node import Node
from sqlalchemy.dialects import registry

pd.options.display.max_columns = None
pd.options.display.max_rows = None


class DB:
    def __init__(
        self,
        connection_url="",
        ssh_command: str = None,
        conf: dict = None,
        connection_file: str = None,
        rc: str = None,
    ):
        self.connection_string = connection_url
        self.ssh_command = ssh_command
        self._connect_with_dict_or_file(conf, connection_file,rc)
        self.engine = create_engine(self.connection_string)
        self.Session = sessionmaker(bind=self.engine)

    def testCipher(self):
        engine = create_engine(self.connection_string)
        connection = engine.connect()
        connection.close()

    def _connect_with_dict_or_file(self, conf, filename,resource):
        def action(x):
            if isinstance(x, dict):
                db=x.get('db',Node(x).get(f'{resource}.db')) 
                if db:
                    self.ssh_command = db.get("ssh")
                    self.connection_string = db.get("url")
            return x

        home=str(Path.home())
        filename=filename if filename else f"{home}/.db.yml" if resource else None;
        conf = fn.file_dict(filename) if filename else conf
        return fn.walk(conf, action) if conf else None

    def open_ssh(self, key_file):
        cmd = self.ssh_command + f" -i {key_file}"
        return fn.run_cmd(cmd)

    def ssh_run(self, sql_func=None, *args, key_file=None, ssh_wait=5, **kwargs):
        key_file = key_file if key_file is not None else f"{Path.home()}/.ssh/id_rsa"
        func = sql_func if sql_func is not None else self.tables
        if self.ssh_command is None or self.ssh_command.lower() == 'no':
            return func(*args, **kwargs)
        with self.open_ssh(key_file) as con:
            try:
                con.wait(ssh_wait)
                results = func(*args, **kwargs)
            except Exception as e:
                print(f"Error executing query: {e}")
        self.engine.dispose()
        return results

    def exec(self, query, params=None):
        query = self._bind(query)
        with self.Session() as session:
            try:
                session.execute(text(query), params)
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Error executing query: {e}")

    def sExecFile(self, filename, params=None):
        with open(filename,'r') as file:
            return self.ssh_run(self.exec,file.read(),params)
            
    def _bind(self,sql,params=None):
        if params is None:
            return sql
        for key in params:
           sql=re.sub(f"'\[\s*{key}\s*]'",f" :{key}",sql) 
        return sql
    
    def query(self, query, params=None):
        query = self._bind(query,params)
        return pd.read_sql_query(text(query), self.engine, params=params)

    def squery(self, query, params=None):
        return self.ssh_run(self.query, query, params)

    def file(self, filename, params=None):
        with open(filename, "r") as file:
            return self.query(file.read(), params)

    def sfile(self, filename, params=None):
        return self.ssh_run(self.file, filename, params)

    def tables(self, schema="public"):
        query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"
        return self.query(query)

    def views(self, schema="public"):
        query = f"SELECT table_name FROM information_schema.views WHERE table_schema = '{schema}'"
        return self.query(query)

    def table(self, table_name, schema="public"):
        sql_file = pkg.resource_filename("dihlibs", "data/describe_table.sql")
        return self.file(sql_file, {"table": table_name, "schema": schema})

    def view(self, view_name):
        return self.query(
            f"SELECT definition FROM pg_views WHERE viewname = '{view_name}'"
        )

    def select_part_matview(self, sql_file):
        sql = fn.text(sql_file)
        regex = r"create mater[^\(]*\(([^;]+)\)"
        select = re.findall(regex, sql, re.MULTILINE | re.IGNORECASE)
        return select[0] if select else sql

    def quote_columns_names(self, names):
        return [f'"{n}"' if " " in n else n for n in names]

    def ssh_upate_table_df(self, df, tablename, id_column="id",on_conflict=""):
        return self.ssh_run( self.upate_table_df,df,tablename,id_column,on_conflict)

    def _format_value(self, value, dtype):
        if pd.isna(value):  # Handle NaN values
            return "NULL"
        elif pd.api.types.is_numeric_dtype(dtype):
            return str(value)
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'::TIMESTAMP"
        else:  # Default to string
            v=str(value).replace("'", "''");
            return f"'{v}'"

    def upate_table_df(self, df, tablename, id_column="id",on_conflict=''):
        df=df.copy()
        db_columns = self.quote_columns_names(df.columns)
        columns = ",".join(db_columns)
        update_columns = ",".join([f"temp.{c}" for c in db_columns])
        set_columns = ",\n".join([f"{c}=temp.{c}" for c in db_columns])

        # Create SQL values string with proper formatting
        for c, dtype in zip(df.columns, df.dtypes):
            df[c] = df[c].apply(lambda v: self._format_value(v, dtype))
        values = df.apply(lambda r: f"({','.join(map(str, r.values))})", axis=1)

        sql_file = pkg.resource_filename("dihlibs", "data/df_update_table.sql")
        sql = Path(sql_file).read_text()
        sql = sql.format(
            tablename=tablename,
            columns=columns,
            set_columns=set_columns,
            update_columns=update_columns,
            id_column=id_column,
            values=",\n".join(values),
            on_conflict=on_conflict,
        )
        return self.exec(sql)

    # registry.register("sqlcipher", "dihlibs.SQLCipherDialect", "SQLCipherDialect")