import pandas as pd
import re
import requests as rq



class DHIS:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.orgs = self.__get_org_units()
        self.combos = self.__get_category_combos()

    def __normalize_combo(self, input):
        c = input.lower()
        c = re.sub(r"(default(.+)|(.+)default)", r"\2\3", c)
        c = re.sub(r"(\d+)\D+(\d+)?\s*(year|mon|week|day)\w+", r"\1-\2\3", c)
        c = re.sub(r"(\d+)\D*(trimester).*", r"\1_\2", c)
        return ",".join(sorted([x.strip() for x in c.split(",") if x]))

    def __get_category_combos(self):
        url = f"{self.base_url}/api/categoryOptionCombos?paging=false&fields=id~rename(categoryOptionCombo),displayName~rename(combo)"
        cmb = pd.json_normalize(rq.get(url).json()["categoryOptionCombos"])
        cmb["disaggregation_value"] = cmb.combo.apply(self.__normalize_combo)
        return cmb.drop(columns="combo")

    def __get_org_units(self):
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
        ).apply(self.__normalize_combo)
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

    def __log_response(self,rs,dot=True):
        if dot and rs.status_code == 200 or rs.status_code==201: 
            print(".", end="", flush=True)
        else: print(rs.text)    
        return rs.json().get('status')

    def _upload_org(self, dataset_id, data: pd.DataFrame):
        url = f"{self.base_url}/api/dataValueSets?dataSet={dataset_id}"
        data = data.drop_duplicates()
        data = data[data.value.notna()].reset_index(drop=True)
        dv=data[["orgUnit", "period"]].drop_duplicates();
        payload = dv.to_dict(orient="records")[0]
        payload.update(
            {
                "dataSet": dataset_id,
                "completeData": True,
                "overwrite": True,
                "dataValues": data[ ["dataElement", "categoryOptionCombo", "value"] ].to_dict(orient="records"),
            }
        )
        return self.__log_response(rq.post(url, json=payload))

    def upload_orgs(self, dataset_id, org_names: list, data):
        return [self._upload_org(dataset_id, data[data.orgUnit == n]) for n in org_names]

    def refresh_analytics(self):
        url = f"{self.base_url}/api/resourceTables/analytics"
        r = rq.post(url).json()
        print(r.get("status"), r.get("message"))
        return r.get("status")

    class Results:
        def __init__(self):
            self.summary = {}

        def add(self, ds_id, results):
            ds = self.summary.setdefault(ds_id, {"success": 0, "error": 0})
            ds["success"] += results.count("OK")
            ds["error"] += len(results) - results.count("OK")

        def send_to_slack(self, webhook_url, month: str, labels: pd.DataFrame):
            lb = labels.drop_duplicates()
            lb = lb.set_index("dataset_id")["dataset_name"].to_dict()
            msg = [f"*JnA DHIS uploaded results for `{month}`*", "", ""]
            for id_category, counts in self.summary.items():
                msg.append(lb.get(id_category))
                msg.append(f"\t\u2022\tSuccess: {counts['success']}")
                msg.append(f"\t\u2022\tError: {counts['error']}")
                msg.append("")  # Add an empty line after each ID category
            return rq.post(webhook_url, json={"text": "\n".join(msg)})
