import os, sys
import pandas as pd
import sqlalchemy
import requests

import dihlibs.dhis.dhis as dh
import dihlibs.query
import dihlibs.utils as fn
import dihlibs.cron_logger as logger
import dihlibs.drive as gd

log = None


def _download_matview_data(postgres_url: str, month: str, e_map: pd.DataFrame):
    log.info("Now starting to download data from sql view...")
    with fn.run_cmd("ssh -4 -T medic-db") as shell:
        log.info(shell.results)
        with sqlalchemy.create_engine(postgres_url).connect() as con:
            for db_view in e_map.db_view.unique():
                log.info(f"    .....downloading: {db_view}")
                data = pd.read_sql(sqlalchemy.text(query.get_sql(db_view, month)), con)
                if not os.path.exists(".data/views"):
                    os.makedirs(".data/views")
                data.to_csv(f".data/views/{db_view}-{month}.csv", index=False)
    e_map.to_csv(f".data/element_map-{month}.csv")


def _change_columns_include_tablename(file_name, df):
    common = ["orgUnit", "categoryOptionCombo", "period"]
    db_view = file_name.split("-")[0]
    log.info(f"    .... processing {db_view}")
    df.columns = [x if x in common else f"{db_view}_{x}" for x in df.columns]
    return df


def _process_downloaded_data(dhis: object, month: str, e_map: pd.DataFrame):
    log.info("Starting to convert into DHIS2 payload ....")
    common = ["orgUnit", "categoryOptionCombo", "period"]
    data = pd.DataFrame(columns=common)
    files = [file for file in os.listdir(".data/views") if month in file]
    for file in files:
        df = pd.read_csv(f".data/views/{file}")
        df["period"] = pd.to_datetime(df.reported_month).dt.strftime("%Y%m")
        df = dhis.add_category_combos_id(df)
        df = dhis.add_org_unit_id(df)
        df = df.dropna(subset=["orgUnit"])
        df = _change_columns_include_tablename(file, df)
        data = data.merge(df, how="outer", on=common)
    return dhis.to_data_values(data, e_map)


def _upload(
    dhis: dh.DHIS,
    data: pd.DataFrame,
):
    log.info("Starting to upload payload...")
    res = dhis.Results()
    for ds_id in data.dataSet.unique():
        log.info(f"\nuploading to dataset with id: {ds_id}")
        ds = data[data.dataSet == ds_id].drop("dataSet", axis=1).reset_index(drop=True)
        fn.do_chunks(
            source=ds.orgUnit.unique(),
            chunk_size=10,
            func=lambda orgs_names: dhis.upload_orgs(ds_id, orgs_names, data),
            consumer_func=lambda _, v: res.add(ds_id, v),
            thread_count=16,
        )
        log.info("\n")
    return res


def _get_the_mapping_file(conf: object):
    log.info("seeking mapping file from google drive ....")
    e_map = gd.Drive(conf.drive_key).get_df(conf.e_map_google, "data_elements")
    # e_map = pd.read_csv("./.data/element_map-2023-04-01.csv")
    e_map = e_map[e_map.db_column.notna() & e_map.element_id.notna()].copy()
    e_map["map_key"] = e_map.db_view + "_" + e_map.db_column
    return e_map.set_index("map_key")

def notify_on_slack(conf:object,message:dict):
    if conf.notification!= 'on': return;
    res=requests.post(conf.slack_webhook_url,message)
    print('slack text status',res.status_code,res.text)
    lpk,.7



def main(
    config_file="/etc/cronies/config/dhis-config.json",
    month=fn.get_month(-1),
    task_name="",
):
    global log
    log = logger.get_logger_task(task_name)
    log.info(f"initiating.. for the period {month}")
    log.info("loading the config")
    conf = fn.get_config(config_file=config_file)
    try: 
        log.info(f"initiating connection dhis ... ")
        dhis = dh.DHIS(conf.dhis_url)
        e_map = _get_the_mapping_file(conf)
        _download_matview_data(conf.postgres_url, month, e_map)
        data = _process_downloaded_data(dhis, month, e_map)
        res = _upload(dhis, data)
        log.info("Starting to refresh analytics ...")
        dhis.refresh_analytics()

        if conf.notifications == "on":
            log.info("Now sending summary to slack")
            url = conf.slack_webhook_url
            labels = e_map[["dataset_id", "dataset_name"]]
            res.send_to_slack(url, month, labels)
    except Exception as e:
        slack=conf.slack_webhoot_url


if __name__ == "__main__":
    main()
