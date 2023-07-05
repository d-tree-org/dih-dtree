import pandas as pd, numpy as np
import re
import requests
from datetime import datetime


def fill_the_parental_column_gaps(df: pd.DataFrame):
    df = df.copy()
    for i in range(len(df.columns) - 1, 0, -1):
        current_col = df.columns[i - 1]
        next_col = df.columns[i]
        notna_indices = df[next_col].notna()
        df[current_col] = np.where(
            df[current_col].isnull() & notna_indices,
            df[current_col].ffill(),
            df[current_col],
        )
    return df


def create_id(row, ids={}):
    name = row["name"]
    parent = row["parent"]
    alphanumeric = row.id_prefix + re.sub(r"[\W_]+", "", name)
    id = alphanumeric[0:11] if len(alphanumeric) >= 11 else alphanumeric.ljust(11, "i")

    input = re.sub(r"[\W_]+", "", (name + parent).lower())
    while ids.get(id) != input and id in ids:
        d = id[-1]
        id = id[:-1] + str(int(d) + 1 if d.isdigit() else 2)
    ids[id] = input
    return id


def set_parent_ids(data):
    prefix = {
        "cn": "",
        "mz": "cn",
        "mdh": "mz",
        "mhc": "mdh",
        "mvc": "mhc",
    }
    columns = {
        "name": "ignore",
        "parent": "name",
        "gparent": "parent",
    }
    data["id_prefix"] = data.id_prefix.replace(prefix)
    data["parent"] = (
        data.rename(columns=columns)
        .apply(create_id, axis=1)
        .replace(regex="Glob.*", value="gbglobalZZZ")
        .apply(lambda x: {"id": x})
    )
    return data.drop(columns=["gparent", "id_prefix"])


def make_orgUnits(df):
    prefix = ["cn", "mz", "mdh", "mhc", "mvc"]
    data = pd.DataFrame()
    for i in range(len(df.columns)):
        name = df.iloc[:, i].replace(regex="[^\w\s]+", value="-")
        parent = df.iloc[:, i - 1] if i > 0 else "Global"
        gparent = df.iloc[:, i - 2] if i > 1 else "Global"
        id_pref = pd.Series(prefix[i], index=df.index)
        p = pd.DataFrame(
            {
                "level": i + 2,
                "name": name,
                "shortName": name,
                "parent": parent,
                "gparent": gparent,
                "id_prefix": id_pref,
            }
        ).reset_index(drop=True)
        data = pd.concat([data, p])
    data = data.drop_duplicates(subset=["name"]).dropna(subset=["name"])
    data = data.sort_values(["level", "name"])
    data["id"] = data.apply(create_id, axis=1)
    data["openingDate"] = datetime.today().strftime("%Y-%m-%d")
    return set_parent_ids(data)




if __name__=="__main__":
    df = pd.read_excel("orgs.xlsx", "orgs")
    df = make_orgUnits(fill_the_parental_column_gaps(df))
    url = "http://admin:Ingia.123@localhost/api/metadata"
    payload = {"organisationUnits": df.to_dict(orient="records")}
    rs = requests.post(url, json=payload)
    print(df)
    