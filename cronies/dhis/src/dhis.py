import pandas as pd, numpy as np, re, asyncio, aiohttp, requests as rq, threading, json, sys, os

sys.path.append("../../libs")
import cron_logger as logger
import utils as fn


class DHIS:
    def __init__(self, conf, mapping_file):
        self._log = logger.get_logger_message_only()
        self._log.info(f"initiating connections dhis ... ")
        self.__conf = conf
        self._mapping_file = mapping_file
        self.base_url = conf.dhis_url
        self.orgs = self._get_org_units()
        self.combos = self._get_category_combos()
        self.datasets = self._get_datasets()
        self._log.info(f"dhis reached OK \n")

    def _normalize_combo(self, input):
        c = input.lower().strip()
        c = re.sub(r"(default(.+)|(.+)default)", r"\2\3", c)
        c = re.sub(r"(\d+)\D+(\d+)?\s*(yrs|year|mon|week|day)\w+", r"\1-\2\3", c)
        c = re.sub(r"(\d+)\D*(trimester).*", r"\1_\2", c)
        c = re.sub(r"(\W*,\W*|\Wand\W)", ",", c)
        c = re.sub(r"(\W*to\W*|\s+|\-)", "_", c)
        return ",".join(sorted([x.strip() for x in c.split(",") if x]))

    def _get_datasets(self):
        if os.path.exists(".data/dataSets.json"):
            with open(".data/dataSets.json", "r") as file:
                return pd.DataFrame(json.load(file))

        dataset_ids = ",".join(
            pd.read_excel(self._mapping_file, "data_elements")
            .dataset_id.dropna()
            .unique()
            .tolist()
        )
        url = f"{self.base_url}/api/dataSets?fields=id,name&filter=id:in:[{dataset_ids}]&paging=false"
        return pd.DataFrame(rq.get(url).json()["dataSets"])

    def _get_category_combos(self):
        if "category_option_combos" in self._mapping_file.sheet_names:
            cmb = pd.read_excel(self._mapping_file, "category_option_combos").dropna()
        else:
            url = f"{self.base_url}/api/categoryOptionCombos?paging=false&fields=id,displayName~rename(disaggregationValue),categoryCombo[id,displayName]"
            cmb = pd.json_normalize(rq.get(url).json()["categoryOptionCombos"]).rename(
                columns={
                    "categoryCombo.displayName": "disaggregation",
                    "categoryCombo.id": "disaggregation_id",
                    "disaggregationValue": "disaggregation_value",
                    "id": "categoryOptionCombo",
                }
            )
        cmb["disaggregation"] = cmb["disaggregation"].apply(self._normalize_combo)
        cmb["disaggregation_value"] = cmb["disaggregation_value"].apply(
            self._normalize_combo
        )
        cmb["combined_key"] = cmb.apply(
            lambda row: (row["disaggregation"], row["disaggregation_value"]), axis=1
        )
        return cmb

    def _rename_db_columns(self, df: pd.DataFrame, rename_sh: pd.DataFrame):
        if "rename" not in self._mapping_file.sheet_names:
            return df
        rn = rename_sh[rename_sh.what == "column"]
        column_mapping = dict(zip(rn["db_column"], rn["dhis_name"]))
        df.rename(columns=column_mapping, inplace=True)
        return df

    def rename_db_dhis(self, df: pd.DataFrame):
        if "rename" not in self._mapping_file.sheet_names:
            return df
        df = df.copy()
        rename_sh = pd.read_excel(self._mapping_file, "rename")
        df = self._rename_db_columns(df, rename_sh)
        for n in rename_sh[rename_sh.what == "value"].db_column.unique():
            if n not in df.columns:
                continue
            x = pd.merge(df, rename_sh, how="left", left_on=n, right_on="db_name")
            df[n] = x.dhis_name.fillna(df[n])
        return df

    def __prep_key(self, value):
        if isinstance(value, list):
            return {self.__prep_key(x) for x in value}
        elif isinstance(value, pd.Series):
            return {self.__prep_key(x) for x in value.values}
        elif isinstance(value, str):
            return re.sub(r"\W+", "", value)
        else:
            return value

    def _get_org_units(self):
        def set_location(row):
            return self.__prep_key([x["name"] for x in row.ancestors]) | {
                self.__prep_key(row.orgName)
            }

        if os.path.exists(".data/organisationUnits.json"):
            with open(".data/organisationUnits.json", "r") as file:
                orgs = pd.json_normalize(json.load(file))
        else:
            levels = json.dumps(list(self.__conf.location_levels.values()))
            levels = levels.replace(" ", "")
            url_root = f"{self.base_url}/api/organisationUnits?fields=id,name,level&filter=name:eq:{self.__conf.country}"
            root = rq.get(url_root).json()["organisationUnits"][0]
            url_orgs = f"{self.base_url}/api/organisationUnits?filter=path:like:{root['id']}&filter=level:in:{levels}&fields=id~rename(orgUnit),name~rename(orgName),level,ancestors[name]&paging=false"
            orgs = pd.json_normalize(rq.get(url_orgs).json()["organisationUnits"])
            orgs.to_csv("temp_orgs.csv")

        orgs["name_key"] = orgs.orgName.apply(self.__prep_key)
        orgs["location"] = orgs.apply(set_location, axis=1)
        return orgs

    def add_category_combos_id(self, data: pd.DataFrame):
        # Ensure both disaggregation_value and disaggregation are in the DataFrame
        if "disaggregation_value" not in data.columns.values:
            data["disaggregation_value"] = "default"
        if "disaggregation" not in data.columns.values:
            data["disaggregation"] = "default"
        # Fill missing values with "default"
        data["disaggregation_value"] = data.disaggregation_value.fillna("default")
        data["disaggregation"] = data.disaggregation.fillna("default")
        # Normalize both columns
        data["disaggregation_value"] = data["disaggregation_value"].apply(
            self._normalize_combo
        )
        data["disaggregation"] = data["disaggregation"].apply(self._normalize_combo)
        data["combined_key"] = data.apply(
            lambda row: (row["disaggregation"], row["disaggregation_value"]), axis=1
        )
        return data.merge(self.combos, how="left", on="combined_key")

    def add_org_unit_id(self, data: pd.DataFrame):
        def find_matching(x):
            s = self.orgs[self.orgs.name_key.isin(x)]
            matches = s[s.location.apply(lambda y: x.issubset(y))]
            return matches.orgUnit.values[0] if matches.size > 0 else pd.NA

        loc = [x for x in data.columns if x in self.__conf.location_levels.keys()]
        data["location"] = data[loc].apply(self.__prep_key, axis=1)
        data["orgUnit"] = data.location.map(find_matching)
        return data

    def to_data_values(self, data: pd.DataFrame, e_map: pd.DataFrame):
        id_vars = ["orgUnit", "categoryOptionCombo", "period"]
        value_vars = [col for col in data.columns if col in e_map.index]
        output = pd.melt(
            data,
            id_vars=id_vars,
            value_vars=value_vars,
            var_name="db_column",
            value_name="value",
        ).dropna(subset=["value"])
        output = output[pd.to_numeric(output.value, errors="coerce").notna()]
        output["dataSet"] = output.db_column.replace(e_map["dataset_id"])
        output["dataElement"] = output.db_column.replace(e_map["element_id"])
        output["value"] = output.value.astype(int)
        output = output.drop_duplicates()
        return output

    async def upload_orgs(self, files:list, upload_summary):
        url = f"{self.base_url}/api/dataValueSets"
        if hasattr(self.__conf, "upload_endpoint"):
            url = self.__conf.upload_endpoint

        results = []
        data = map(pd.read_csv, files)
        for org in data:
            org.dropna(subset=["value"], inplace=True)
            org.dropna(subset=["categoryOptionCombo"], inplace=True)
            org.dropna(subset=["dataElement"], inplace=True)
            values = org[["dataSet","dataElement", "categoryOptionCombo", "value"]].to_dict(
                orient="records"
            )
            payload = {
                "orgUnit": org["orgUnit"].iloc[0],
                "period": org["period"].iloc[0],
                "completeData": True,
                "overwrite": True,
                "dataValues": values,
            }
            rs=await _post_data(url,payload,dot=True)
            results.append(rs)
        upload_summary.add(results)

    def refresh_analytics(self):
        if self.__conf.run_analytics != "on":
            return
        self._log.info("Starting to refresh analytics ...")
        resp = rq.post(f"{self.base_url}/api/resourceTables/analytics").json()
        self._log.info(f' Analytics: {resp.get("status")}, {resp.get("message")}')
        return resp.get("status")


_log = logger.get_logger_message_only()
log_lock = asyncio.Lock()

async def _post_data(url,payload, dot=True):
    async with log_lock:  # Use an async with block for the asyncio.Lock
        try:
            results = await fn.post(url,payload)
            if dot:
                _log.info(".")
            return results.get("status")
        except Exception as error:
            _log.error(error)


class UploadSummary:
    def __init__(self, dhis: DHIS):
        self.summary = {"success": 0, "error": 0}

    def add(self,results):
        self.summary["success"] += results.count("OK")
        self.summary["error"] += len(results) - results.count("OK")

    def get_slack_post(self, month: str):
        msg = [f"*JnA DHIS uploaded results for `{month}`*", "", ""]
        msg.extend(
            [
                f'Total of {self.summary["error"] + self.summary["success"]} organisation Units were processed and:',
                f"\t\u2022\tSuccess: {self.summary['success']}",
                f"\t\u2022\tError: {self.summary['error']}",
                "",
            ]
        )
        return {"text": "\n".join(msg)}
