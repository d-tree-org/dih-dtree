import os, sys
import pandas as pd
import sqlalchemy

sys.path.append("../../libs")
from dhis import DHIS, UploadSummary
from db import DB
import utils as fn
import cron_logger as logger
import drive as gd
import requests, asyncio
from functools import partial


log = None


def download_matview_data(view_name, month: str, db: DB):
    db_view_name = view_name[0]
    matview = db_view_name
    if "sql_" in db_view_name:
        sql = db.select_part_matview(f"sql/{db_view_name[4:]}.sql")
        matview = f"({sql}) as data_cte "

    col = "issued_month" if "referral" in db_view_name else "reported_month"
    sql = f"select * from {matview} where {col}='{month}'"
    db.query(sql).to_csv(f".data/views/{db_view_name}-{month}.csv")
    return f"Downloaded {db_view_name}"


def _download_matview_data(conf: object, month: str, e_map: pd.DataFrame):
    log.info("Starting to download data from SQL view...")
    os.makedirs(".data/views", exist_ok=True)

    with fn.run_cmd(conf.tunnel_ssh) as shell:
        db = DB(conf)
        db_views = list(e_map.db_view.unique())
        fn.do_chunks(
            source=db_views,
            chunk_size=1,  # Each chunk is a single view
            func=partial(download_matview_data, month=month, db=db),
            consumer_func=lambda _, result: log.info(result),
            thread_count=3,  # Adjust based on your environment
        )
    e_map.to_csv(f".data/element_map-{month}.csv")


def _add_tablename_columns(file_name, df):
    common = ["orgUnit", "categoryOptionCombo", "period"]
    db_view = file_name.split("-")[0]
    log.info(f"    .... processing {db_view}")
    df.columns = [x if x in common else f"{db_view}_{x}" for x in df.columns]
    return df


def _save_processed_org(df: pd.DataFrame, month):
    for org in df.orgUnit.unique():
        x = df.loc[df.orgUnit == org, :]
        filepath = f".data/processed/{month}/{org}.csv"
        is_new_file = not os.path.exists(filepath)
        x.to_csv(filepath, index=False, mode="a", header=is_new_file)


def _process_downloaded_data(dhis: DHIS, month: str, e_map: pd.DataFrame):
    log.info("Starting to convert into DHIS2 payload ....")
    files = filter(lambda file: month in file, os.listdir(".data/views"))
    os.makedirs(f".data/processed/{month}", exist_ok=True)
    for file in files:
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
    conf,
    dhis: DHIS,
    month: str,
):
    log.info("Starting to upload payload...")
    folder = f".data/processed/{month}/"
    files = [folder + x for x in os.listdir(folder)]
    summary=UploadSummary(dhis)
    await fn.do_chunks_async(
        source=files,
        chunk_size=10,
        func=partial(dhis.upload_orgs, upload_summary=summary),
    )
    log.info("\n")
    msg = summary.get_slack_post(month)
    notify_on_slack(conf, msg)


def _get_the_mapping_file(excel_file, only_new_elements=False):
    log.info("seeking mapping file from google drive ....")
    e_map = pd.read_excel(excel_file, "data_elements")
    e_map = e_map.dropna(subset=["db_column", "element_id"]).copy()
    e_map["map_key"] = e_map.db_view + "_" + e_map.db_column
    e_map = e_map.set_index("map_key")
    return (
        e_map[e_map.is_new == True] if only_new_elements else e_map[e_map.is_new.isna()]
    )


def notify_on_slack(conf: object, message: dict):
    if conf.notifications != "on":
        log.error(f"for slack: {message}")
        return
    res = requests.post(conf.slack_webhook_url, json=message)
    log.info(f"slack text status,{res.status_code},{res.text}")


def start(
    config_file="/dih/common/configs/${proj}.json",
    month=fn.get_month(-1),
    task_name="",
    only_new_elements=False,
):
    global log
    log = logger.get_logger_task(task_name)
    log.info(f"initiating.. for the period {month} \n .. loading the config")
    conf = fn.get_config(config_file=config_file)
    try:
        drive = gd.Drive(conf.drive_key)
        mapping_file = drive.get_excel(conf.data_element_mapping)
        dhis = DHIS(conf, mapping_file)
        e_map = _get_the_mapping_file(mapping_file, only_new_elements)
        _download_matview_data(conf, month, e_map)
        _process_downloaded_data(dhis, month, e_map)
        asyncio.run(_upload(conf, dhis, month))
        dhis.refresh_analytics()
    except Exception as e:
        log.exception(f"error while runninng for period {month} { str(e) }")
        notify_on_slack(conf, {"text": "ERROR: " + str(e)})


if __name__ == "__main__":
    start()
