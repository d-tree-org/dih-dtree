import os, sys
import pandas as pd
import sqlalchemy
import requests, asyncio
from functools import partial

from dihlibs.dhis import DHIS, UploadSummary
from dihlibs.db import DB, ResultFormat
from dihlibs.dhis.configuration import Configuration
from dihlibs import functions as fn
from dihlibs import cron_logger as logger
from dihlibs import drive as gd
from dihlibs.node import Node
import tempfile


log = None

conf = Configuration()


def download_matview_data(views, db: DB):
    for v in views:
        view = Node(v)
        matview = view.db_view
        if "sql_" in matview:
            sql = db.select_part_matview(f"sql/{matview[4:]}.sql")
            matview = f"({sql}) as data_cte "

        sql = f"select * from {matview} where {view.period_column}='{view.period_db}'"
        db.query(sql,format=ResultFormat.PANDAS).to_csv(f".data/views/{view.db_view}:{view.period}.csv",index=False)
    return f"Downloaded {view.db_view}"


def _download_matview_data(dhis: DHIS):
    os.makedirs(".data/views", exist_ok=True)
    db = DB(conf=conf.conf)
    e_map = conf.get_element_mappings(dhis)
    with tempfile.NamedTemporaryFile(delete=True) as key:
        key.write(conf.get_file("tunnel"))
        key.flush()
        db.ssh_run(
            fn.do_chunks,
            source=e_map.drop_duplicates(subset="db_view").to_dict(orient="records"),
            chunk_size=1,  # Each chunk is a single view
            func=partial(download_matview_data, db=db),
            consumer_func=lambda _, results: log.info(results),
            thread_count=10,
            key_file=key.name,
        )


def _add_tablename_columns(file_name, df):
    common = ["orgUnit", "categoryOptionCombo", "period"]
    db_view = file_name.split("-")[0]
    df.columns = [x if x in common else f"{db_view}_{x}" for x in df.columns]
    return df


def clear_old_files(e_map):
    folder='.data/processed/'
    for _, m in e_map.drop_duplicates(subset="db_view").iterrows():
        file_to_clear = [folder + f for f in os.listdir(folder) if m.period in f and os.path.isfile(folder+f) ]
        for file in file_to_clear:
            os.unlink(file)

def _save_processed_org(df: pd.DataFrame, period):
    for org in df.orgUnit.unique():
        x = df.loc[df.orgUnit == org, :]
        filepath = f".data/processed/{period}:{org}.csv"
        is_new_file = not os.path.exists(filepath)
        x.to_csv(filepath, index=False, mode="a", header=is_new_file)
        


def _process_downloaded_data(dhis: DHIS):
    log.info("Starting to convert into DHIS2 payload ....")
    os.makedirs(f".data/processed/", exist_ok=True)
    e_map = conf.get_element_mappings(dhis)
    clear_old_files(e_map)
    x=0;
    for _, m in e_map.drop_duplicates(subset="db_view").iterrows():
        file = f".data/views/{m.db_view}:{m.period}.csv"
        if not os.path.isfile(file):
            continue
        log.info(f"    .... processing {file}")
        x=x+1
        df = pd.read_csv(file)
        df = dhis.rename_db_dhis(df)
        df = df.dropna(subset=m.period_column)
        df["period"] = m.period
        df = dhis.add_category_combos_id(df)
        df = df.dropna(subset=["categoryOptionCombo"])
        df = dhis.add_org_unit_id(df)
        df = df.dropna(subset=["orgUnit"])
        df = _add_tablename_columns(m.db_view, df)
        df = dhis.to_data_values(df, e_map)
        _save_processed_org(df, m.period)


async def _upload(dhis: DHIS):
    log.info("Starting to upload payload...")

    periods = conf.get_element_mappings(dhis).period.drop_duplicates().tolist()
    folder = f".data/processed/"
    files = [folder + f for f in os.listdir(folder) if f.split(":")[0] in periods]
    summary = UploadSummary(dhis)
    await fn.do_chunks_async(
        source=files,
        chunk_size=80,
        func=partial(dhis.upload_org, upload_summary=summary),
    )
    log.info("\n")
    msg = summary.get_slack_post(", ".join(periods))
    notify_on_slack(msg)


def notify_on_slack(message: dict):
    if conf.get("notifications") != "on":
        log.error(f"for slack: {message}")
        return
    res = requests.post(conf.get("slack_webhook_url"), json=message)
    log.info(f"slack text status,{res.status_code},{res.text}")


def start():
    global log
    log = logger.get_logger_task(conf.get("task_dir"))
    log.info(f"Initiating..")
    try:
        dhis = DHIS(conf)
        _download_matview_data(dhis)
        _process_downloaded_data(dhis)
        asyncio.run(_upload(dhis))
        dhis.refresh_analytics()
    except Exception as e:
        log.exception(f"error while runninng for period {conf.get('month')} { str(e) }")
        notify_on_slack({"text": "ERROR: " + str(e)})


if __name__ == "__main__":
    start()
