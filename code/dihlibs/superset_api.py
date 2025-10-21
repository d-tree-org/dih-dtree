import requests
import dihlibs.functions as fn
from dihlibs.node import Node
import json
from functools import wraps
from dihlibs.jsonq import JsonQ
import pandas as pd,re
from io import StringIO

class SupersetAPI:
    def __init__(self, rc, file="db_connections"):
        self.file = file
        self.rc = rc
        self.headers = {}
        self.access_token = None
        self._refresh_token = None
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
        )
        if response.status_code != 200:
            return response
        data = response.json()
        self.access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        return response

    def refresh_access_token(self):
        if not self._refresh_token:
            return False
        refresh_url = f"{self.url}/api/v1/security/refresh"
        resp = requests.post(refresh_url, json={"refresh_token": self._refresh_token})
        if resp.status_code != 200:
            return False
        data = resp.json()
        self.access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        return self.access_token is not None

    def ensure_authenticated(self):
        """Ensures the session is authenticated before making requests."""
        if not self.access_token:
            print('ensuring auth...attempting to log in first')
            response = self.login()
            return response is not None and response.status_code == 200 and self.access_token
        elif fn.has_expired_client_side(self.access_token):
            print('ensuring auth...token has expired, refreshing it first')
            return self.refresh_access_token()
        return True

    def retry_on_auth_failure(func):
        """Decorator to handle session expiration and retry authentication."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.ensure_authenticated():
                print("Could not authenicate, so exiting")
                return
            response = func(self, *args, **kwargs)
            if response is not None and response.status_code in [401, 403]:  # Session expired
                print('retrying..')
                login_response = self.login()
                if login_response is not None and login_response.status_code == 200:
                    response = func(self, *args, **kwargs)
            return response

        return wrapper

    @retry_on_auth_failure
    def post(self, url, *args, **kwargs):
        headers = {**self.headers, "Authorization": f"Bearer {self.access_token}"}
        return requests.post(self.url + url, *args, headers=headers, **kwargs)

    @retry_on_auth_failure
    def get(self, url, *args, **kwargs):
        headers = {**self.headers, "Authorization": f"Bearer {self.access_token}"}
        return requests.get(self.url + url, *args, headers=headers, **kwargs)
    
    def fetch_dashboard(self,name):
        return self.list_dashboards().get(f"[?(@.dashboard_title ~ '{name}')]");

    def list_dashboards(self):
        """Fetches a list of dashboards."""
        return JsonQ.from_response(self.get( "/api/v1/dashboard/")).get('result')

    def list_charts(self,dashboard,chart_names):
        """Fetches a list of charts."""
        expr = " || ".join(
              f"""
                (@.chart_name && @.chart_name~'{name}') 
                || (@.slice_name && @.slice_name ~ '{name}')
                || (@.slice_name && @.slice_name ~ '{name}')
                """.replace('\n','')
              for name in chart_names
          )
        rs=self.get(f"/api/v1/dashboard/{dashboard.str("id")}/charts")
        return JsonQ.from_response(rs).get(f'result[?({expr})]')
       

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

    def fetch_chart_data(self, dashboard,chart_name, filters):
        chart=self.list_charts(dashboard,[chart_name])
        resp = JsonQ.from_response(self.get(f"/api/v1/chart/{chart.str('id')}"))
        query = JsonQ.from_json(resp.get('result.query_context').root)
        query.merge_many({
           'queries[*].filters': filters,
           'result_format':'csv',
           'result_type':'full',})
        resp = self.post("/api/v1/chart/data", json=query.root)
        df=pd.read_csv(StringIO(resp.text),dtype=str)
        df.columns=[re.sub(r'\W+','_',col.strip()).lower() for col in df.columns]
        return df 