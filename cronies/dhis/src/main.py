import os, sys
import pandas as pd
import sqlalchemy

sys.path.append("../../libs")
from dhis import DHIS,UploadSummary
import query
import utils as fn
import cron_logger as logger
import drive as gd
import requests

log = None

def _download_matview_data(conf: object, month: str, e_map: pd.DataFrame):
    log.info("Now starting to download data from sql view...")
    cmd = conf.tunnel_ssh if 'off'!=conf.tunnel_ssh and conf.tunnel_ssh else "echo running sql without opening ssh-tunnel"
    with fn.run_cmd(cmd) as shell:
        log.info(shell.results)
        with sqlalchemy.create_engine(conf.postgres_url).connect() as con:
            for db_view in e_map.db_view.unique():
                log.info(f"    .....downloading: {db_view}")
                q=query.get_sql(db_view, month)
                data = pd.read_sql(sqlalchemy.text(q), con)
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


def _process_downloaded_data(dhis: DHIS, month: str, e_map: pd.DataFrame):
    log.info("Starting to convert into DHIS2 payload ....")
    common = ["orgUnit", "categoryOptionCombo", "period"]
    data = pd.DataFrame(columns=common)
    files = [file for file in os.listdir(".data/views") if month in file]
    for file in files:
        df = pd.read_csv(f".data/views/{file}")
        df["period"] = pd.to_datetime(df.reported_month).dt.strftime("%Y%m")
        df = dhis.rename_db_values(df)
        df = dhis.add_category_combos_id(df)
        df = dhis.add_org_unit_id(df)
        df = df.dropna(subset=["orgUnit"])
        df = _change_columns_include_tablename(file, df)
        data = data.merge(df, how="outer", on=common)
    return dhis.to_data_values(data, e_map)


def _upload(
    dhis: DHIS,
    data: pd.DataFrame,
):
    log.info("Starting to upload payload...")
    upload_summary = UploadSummary(dhis)
    for ds_id in data.dataSet.unique():
        log.info(f"\nuploading to dataset with id: {ds_id}")
        ds = data[data.dataSet == ds_id].drop("dataSet", axis=1).reset_index(drop=True)
        fn.do_chunks(
            source=ds.orgUnit.unique(),
            chunk_size=10,
            func=lambda orgs_names: dhis.upload_orgs(ds_id, orgs_names, data),
            consumer_func=lambda _, v: upload_summary.add(ds_id, v),
            thread_count=16,
        )
        log.info("\n")
    return upload_summary


def _get_the_mapping_file(excel_file,only_new_elements=False):
    log.info("seeking mapping file from google drive ....")
    e_map=pd.read_excel(excel_file,'data_elements')
    e_map=e_map.dropna(subset=['db_column','element_id']).copy()
    e_map["map_key"] = e_map.db_view + "_" + e_map.db_column
    e_map=e_map.set_index("map_key")
    return e_map[e_map.is_new==True] if only_new_elements else e_map[e_map.is_new.isna()]


def notify_on_slack(conf:object,message:dict):
    if conf.notifications != 'on':
       log.error(f'for slack: {message}') 
       return;
    res=requests.post(conf.slack_webhook_url,json=message)
    log.info(f'slack text status,{res.status_code},{res.text}')


def start(
    config_file="/dih/common/configs/${proj}.json",
    month=fn.get_month(-1),
    task_name="",
    only_new_elements=False
):
    global log
    log = logger.get_logger_task(task_name)
    log.info(f"initiating.. for the period {month} \n .. loading the config")
    conf = fn.get_config(config_file=config_file)
    try: 
        mapping_file=pd.ExcelFile(gd.Drive(conf.drive_key).download_excel_file(conf.data_element_mapping))
        e_map = _get_the_mapping_file(mapping_file,only_new_elements)
        log.info(f"initiating connection dhis ... ")
        dhis = DHIS(conf,mapping_file)
        _download_matview_data(conf, month, e_map)
        data = _process_downloaded_data(dhis, month, e_map)
        data.to_csv('uploaded.csv')
        res = _upload(dhis, data)
        msg=res.get_slack_post(month)
        notify_on_slack(conf,msg)
        if conf.run_analytics=='on':
            log.info("Starting to refresh analytics ...")
            dhis.refresh_analytics()

    except Exception as e:
        log.exception(f"error while runninng for period {month} { str(e) }") 
        notify_on_slack(conf,{'text':'ERROR: ' + str(e)})

if __name__ == "__main__":
    start()