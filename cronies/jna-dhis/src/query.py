import re
import utils as fn


def __get_db_view(db_view_name):
    if "sql_" not in db_view_name:return db_view_name
    sql = fn.file_text(f"sql/{db_view_name[4:]}.sql")
    sql = re.findall("create mater[^\(]*\(([^;]+)\)", sql,re.MULTILINE|re.IGNORECASE)[0]
    return f" ({sql}) as data_cte " 



def get_sql(db_view_name: str, month: str):
    db_view=__get_db_view(db_view_name)
    if "referral" in db_view_name:
        return f"select *,issued_month as reported_month from {db_view} where issued_month='{month}'"
    else:
        return f"select * from {db_view} where reported_month='{month}'"

