import re,sys
sys.path.append("../../libs")
import utils as fn


def _get_db_view(db_view_name):
    if "sql_" not in db_view_name:return db_view_name
    sql = fn.file_text(f"sql/{db_view_name[4:]}.sql")
    sql = re.findall("create mater[^\(]*\(([^;]+)\)", sql,re.MULTILINE|re.IGNORECASE)[0]
    return f" ({sql}) as data_cte " 



def get_sql(db_view_name: str, month: str):
    db_view=_get_db_view(db_view_name)
    col='reported_month' if 'referral' not in db_view_name else 'issued_month'
    return f"select * from {db_view} where {col}='{month}'"

