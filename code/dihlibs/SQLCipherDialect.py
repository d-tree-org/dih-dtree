from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.engine.url import make_url
import pysqlcipher3.dbapi2 as sqlcipher
import dihlibs.functions as fn


class SQLCipherDialect(SQLiteDialect):
    name = "sqlcipher"
    driver = "pysqlcipher3"
    paramstyle = "qmark"
    supports_statement_cache = True
    key = None

    @classmethod
    def dbapi(cls):
        return sqlcipher

    def create_connect_args(self, url):
        parsed_url = make_url(url)
        self.key = parsed_url.query.get("key", None)
        self._adb_pulldb_if_android_db(parsed_url)
        opts = url.translate_connect_args()
        opts.pop("key", None)
        return [[], opts]

    def connect(self, *cargs, **cparams):
        dbapi_con = super().connect(*cargs, **cparams)
        if self.key:
            dbapi_con.execute(f"PRAGMA key='{self.key}';")
        return dbapi_con

    def _adb_pulldb_if_android_db(self, parsed_url):
        package = parsed_url.query.get("package", None)
        if not package:
            return
        db = parsed_url.database
        cmd = f"$HOME/Android/Sdk/platform-tools/adb exec-out run-as {package}  cat /data/data/{package}/databases/{db} > ./{db} "
        print(fn.cmd_wait(cmd))
