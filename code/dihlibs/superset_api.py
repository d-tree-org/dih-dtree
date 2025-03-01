import requests
import dihlibs.functions as fn
from dihlibs.node import Node
import json
from functools import wraps

class SupersetAPI:
    def __init__(self, rc, file="db_connections"):
        self.file = file
        self.rc = rc
        self.headers = {}
        self.access_token = None
        self.url = None

    def login(self):
        """Logs in to Superset and starts a session."""
        cred = Node(fn.load_secret_file(self.file)).get(self.rc)
        self.url = cred.get("url").strip("/")
        payload = {
            "username": cred.get("username"),
            "password": cred.get("password"),
            "refresh": True,
            "provider": "db",
        }
        response = requests.post(
            self.url + "/api/v1/security/login", json=payload
        ).json()
        self.access_token=response.get("access_token")
        self.refresh_token = response.get("refresh_token")
        return self.access_token is not None

    def refresh_token(self):
        url = "/api/v1/security/refresh"
        refresh_payload = json.dumps({"refresh_token": self.refresh_token})
        resp = self.post(url, data=refresh_payload)
        self.access_token=resp.get("access_token")
        return self.access_token is not None

    def ensure_authenticated(self):
        """Ensures the session is authenticated before making requests."""
        if not self.access_token:
            print('ensuring auth...attempting to log in first')
            return self.login()
        elif fn.has_expired_client_side(self.access_token):
            print('ensuring auth...token has expired, refreshing it first')
            return self.refresh_token()
        return True

    def retry_on_auth_failure(func):
        """Decorator to handle session expiration and retry authentication."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.ensure_authenticated():
                print("Could not authenicate, so exiting")
                return
            response = func(self, *args, **kwargs)
            if response.status_code in [401, 403]:  # Session expired
                print('retrying..')
                if self.login().status_code == 200:  # Re-login and retry
                    response = func(self, *args, **kwargs)
            return response

        return wrapper

    @retry_on_auth_failure
    def post(self, url, *args, **kwargs):
        self.headers["Authorization"]= f"Bearer {self.access_token}"
        return requests.post(self.url + url, *args,headers=self.headers, **kwargs)

    @retry_on_auth_failure
    def get(self, url, *args, **kwargs):
        self.headers["Authorization"]= f"Bearer {self.access_token}"
        return requests.get(self.url + url, *args,headers=self.headers, **kwargs)

    def list_dashboards(self):
        """Fetches a list of dashboards."""
        return self.get( "/api/v1/dashboard/")

    def export_dashboards(self, dashboard_ids: list, export_filename="dashboards.zip"):
        """Exports dashboards and saves them as a ZIP file."""
        export_url = f"/api/v1/dashboard/export?q={json.dumps(dashboard_ids)}"
        response = self.get(export_url)
        if response.status_code == 200:
            with open(f"{export_filename}", "wb") as file:
                file.write(response.content)
        return response

    def import_dashboards(self, import_file="dashboards.zip", passwords={}):
        """Imports dashboards from a ZIP file."""
        url = f"/api/v1/dashboard/import"
        files = { "formData": ("dashboard.zip", open(import_file, "rb"), "application/zip")}
        passwords = {f"databases/{k}.yaml": v for k, v in passwords.items()}
        data = {
            "passwords": json.dumps(passwords),
            "overwrite": "true",
        }
        return self.post(url, files=files, data=data)

    def copy_dashboard(self, from_sa, dashboard_ids, passwords={}):
        res = from_sa.export_dashboards(
            dashboard_ids, export_filename="cp_dashboards.zip"
        )
        if res.status_code == 200:
            return self.import_dashboards(
                import_file="cp_dashboards.zip", passwords=passwords
            )
        else:
            print(res.text)

    def get_chart_data(self, dataset_id,columns, filters, extras=None):
        payload = {
            "queries": [{ "columns":columns, "filters":filters,"extras":extras} ],
            "result_format": "csv",
            "result_type": "full",
            "datasource":{"id":dataset_id,"type":"table"}
        }
        # print(json.dumps(payload,indent=2))
        return self.post("/api/v1/chart/data", json=payload)

    # def copy_chart_to_table():
    #     try:
    #         a = sa.get_chart_data(166,columns=['chw_name','visits','registrations',"ward",'event_date','region','provider_id'],filters=filters )
    #         df=pd.read_csv(StringIO(a.text))
    #         df['event_date']=pd.to_datetime(df.event_date,format="%Y-%m-%d")
    #         x=db.secure.update_table_df(df=df,tablename='ucs.chw_performance',id_columns=['provider_id','event_date'])
    #         print(x)
    #     except Exception as e:
    #         print(e)