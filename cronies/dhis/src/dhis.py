import pandas as pd, re, requests as rq, threading,json,sys
sys.path.append("../../libs")
import cron_logger as logger


class DHIS:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.orgs = self._get_org_units()
        self.combos = self._get_category_combos()
        self._log = logger.get_logger_message_only()

    def _normalize_combo(self, input):
        c = input.lower()
        c = re.sub(r"(default(.+)|(.+)default)", r"\2\3", c)
        c = re.sub(r"(\d+)\D+(\d+)?\s*(year|mon|week|day)\w+", r"\1-\2\3", c)
        c = re.sub(r"(\d+)\D*(trimester).*", r"\1_\2", c)
        return ",".join(sorted([x.strip() for x in c.split(",") if x]))

    def _get_category_combos(self):
        url = f"{self.base_url}/api/categoryOptionCombos?paging=false&fields=id~rename(categoryOptionCombo),displayName~rename(combo)"
        cmb = pd.json_normalize(rq.get(url).json()["categoryOptionCombos"])
        cmb["disaggregation_value"] = cmb.combo.apply(self._normalize_combo)
        return cmb.drop(columns="combo")

    def _get_org_units(self):
        url = f"{self.base_url}/api/organisationUnits?filter=level:in:[5,8,7]&fields=id~rename(orgUnit),name~rename(lookup),level,ancestors[name]&paging=false"
        orgs = pd.json_normalize(rq.get(url).json()["organisationUnits"])
        orgs.loc[orgs.level == 8, "lookup"] = orgs[orgs.level == 8].apply(
            lambda x: x.ancestors[4]["name"] + "." + x.lookup, axis=1
        )
        return orgs.drop(columns=["ancestors", "level"])

    def add_category_combos_id(self, data: pd.DataFrame):
        if "disaggregation_value" not in data.columns.values:
            data["disaggregation_value"] = "default"
        data["disaggregation_value"] = data.disaggregation_value.fillna(
            "default"
        ).apply(self._normalize_combo)
        return data.merge(self.combos, how="left", on="disaggregation_value")

    def add_org_unit_id(self, data: pd.DataFrame):
        if "shehia" in data.columns:
            data["lookup"] = data.district + "." + data.shehia
        elif "supervisory_area_uuid" in data.columns:
            data["lookup"] = data.supervisory_area_uuid
        else:
            data["lookup"] = data.district
        return data.merge(self.orgs, how="left", on="lookup")

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
        return output

    def upload_orgs(self, dataset_id, org_names: list, data):
        results = []
        url = f"{self.base_url}/api/dataValueSets?dataSet={dataset_id}"

        for org_name in org_names:
            org = data[data.orgUnit == org_name].copy()
            org.dropna(subset=["value"], inplace=True)
            payload = {
                "orgUnit": org["orgUnit"].iloc[0],
                "period": org["period"].iloc[0],
                "dataSet": dataset_id,
                "completeData": True,
                "overwrite": True,
                "dataValues": org[
                    ["dataElement", "categoryOptionCombo", "value",]
                ].to_dict(orient="records"),
            }
            res=_log_response(rq.post(url, json=payload))
            results.append(res)
        return results

    def refresh_analytics(self):
        resp = rq.post(f"{self.base_url}/api/resourceTables/analytics").json()
        self._log.info(f' Analytics: {resp.get("status")}, {resp.get("message")}')
        return resp.get("status")

    class Results:
        def __init__(self):
            self.summary = {}

        def add(self, ds_id, results):
            ds = self.summary.setdefault(ds_id, {"success": 0, "error": 0})
            ds["success"] += results.count("OK")
            ds["error"] += len(results) - results.count("OK")

        def get_slack_post(self, webhook_url, month: str, labels: pd.DataFrame):
            lb = labels.drop_duplicates()
            lb = lb.set_index("dataset_id")["dataset_name"].to_dict()
            msg = [f"*JnA DHIS uploaded results for `{month}`*", "", ""]
            for id_category, counts in self.summary.items():
                msg.append(lb.get(id_category))
                msg.append(f"\t\u2022\tSuccess: {counts['success']}")
                msg.append(f"\t\u2022\tError: {counts['error']}")
                msg.append("")  # Add an empty line after each ID category
            return {"text": "\n".join(msg)}

        def send_to_slack(self, webhook_url, month: str, labels: pd.DataFrame):
            lb = labels.drop_duplicates()
            lb = lb.set_index("dataset_id")["dataset_name"].to_dict()
            msg = [f"*JnA DHIS uploaded results for `{month}`*", "", ""]
            for id_category, counts in self.summary.items():
                msg.append(lb.get(id_category))
                msg.append(f"\t\u2022\tSuccess: {counts['success']}")
                msg.append(f"\t\u2022\tError: {counts['error']}")
                msg.append("")  # Add an empty line after each ID category
            rs = rq.post(webhook_url, json={"text": "\n".join(msg)})
            return _log_response(rs, dot=False)


_log = logger.get_logger_message_only()
log_lock = threading.Lock()


def _log_response(rs, dot=True):
    with log_lock:
        if rs.status_code != 200 and rs.status_code != 201:
            _log.error(rs.text)
        elif dot:
            _log.info(".")
        else:
            _log.info(rs.text)
        try: return rs.json().get("status")
        except json.decoder.JSONDecodeError:
            _log.error(rs.text)

