import os, sys
import pandas as pd
import sqlalchemy
import requests, asyncio
from functools import partial

from dihlibs.dhis import DHIS, UploadSummary
from dihlibs.db import DB
from dihlibs.dhis.configuration import Configuration
from dihlibs import functions as fn
from dihlibs import cron_logger as logger
from dihlibs import drive as gd
import tempfile


log = None
conf=Configuration()

def download_matview_data(view_names, month: str, db: DB):
    for view_name in view_names:
        matview = view_name
        if "sql_" in view_name:
            sql = db.select_part_matview(f"sql/{view_name[4:]}.sql")
            matview = f"({sql}) as data_cte "

        col = "issued_month" if "referral" in view_name else "reported_month"
        sql = f"select * from {matview} where {col}='{month}'"
        db.query(sql).to_csv(f".data/views/{view_name}-{month}.csv")
    return f"Downloaded {','.join(view_names)}"


def _download_matview_data():
    os.makedirs(".data/views", exist_ok=True)
    db = DB(conf=conf)
    e_map=conf.get('mapping_element')
    month=conf.get('month')
    with tempfile.NamedTemporaryFile(delete=False) as key:
        key.write(conf.get_file('tunnel').encode())
        file_path = key.name  # This holds the absolute path to the temporary file
        with db.open_ssh(file_path) as shell:
            log.info("Starting to download data from SQL view...")
            log.info(shell.wait())
            fn.do_chunks(
                source=e_map.db_view.unique(),
                chunk_size=1,  # Each chunk is a single view
                func=partial(download_matview_data, month=month, db=db),
                consumer_func=lambda _,results:log.info(results),
                thread_count=10
            )
        e_map.to_csv(f".data/element_map-{month}.csv")



def _add_tablename_columns(file_name, df):
    common = ["orgUnit", "categoryOptionCombo", "period"]
    db_view = file_name.split("-")[0]
    df.columns = [x if x in common else f"{db_view}_{x}" for x in df.columns]
    return df


def _save_processed_org(df: pd.DataFrame, month):
    for org in df.orgUnit.unique():
        x = df.loc[df.orgUnit == org, :]
        filepath = f".data/processed/{month}/{org}.csv"
        is_new_file = not os.path.exists(filepath)
        x.to_csv(filepath, index=False, mode="a", header=is_new_file)


def _process_downloaded_data(dhis: DHIS):
    log.info("Starting to convert into DHIS2 payload ....")
    e_map=conf.get('mapping_element')
    month=conf.get('month')
    files = filter(lambda file: month in file, os.listdir(".data/views"))
    os.makedirs(f".data/processed/{month}", exist_ok=True)
    for file in files:
        log.info(f"    .... processing {file}")
        df = pd.read_csv(f".data/views/{file}")
        df = dhis.rename_db_dhis(df)
        df = df.dropna(subset="reported_month")
        df["period"] = pd.to_datetime(df.reported_month).dt.strftime("%Y%m")
        df = dhis.add_category_combos_id(df)
        df = dhis.add_org_unit_id(df)
        df = df.dropna(subset=["orgUnit"])
        df = _add_tablename_columns(file, df)
        df = dhis.to_data_values(df, e_map)
        _save_processed_org(df, month)


async def _upload(
    dhis: DHIS,
):
    month=conf.get('month')
    log.info("Starting to upload payload...")
    folder = f".data/processed/{month}/"
    files = [folder + x for x in os.listdir(folder)]
    summary=UploadSummary(dhis)
    await fn.do_chunks_async(
        source=files,
        chunk_size=80,
        func=partial(dhis.upload_org, upload_summary=summary),
    )
    log.info("\n")
    msg = summary.get_slack_post(month)
    notify_on_slack(msg)


def notify_on_slack(message: dict):
    if conf.get('notifications') != "on":
        log.error(f"for slack: {message}")
        return
    res = requests.post(conf.get('slack_webhook_url'), json=message)
    log.info(f"slack text status,{res.status_code},{res.text}")

def start():
    global log
    log = logger.get_logger_task(conf.get('task_dir'))
    log.info(f"Initiating..")
    try:
        dhis = DHIS(conf)
        _download_matview_data()
        _process_downloaded_data(dhis)
        asyncio.run(_upload(dhis))
        dhis.refresh_analytics()
    except Exception as e:
        log.exception(f"error while runninng for period {conf.get('month')} { str(e) }")
        notify_on_slack({"text": "ERROR: " + str(e)})

if __name__ == "__main__":
    start()

