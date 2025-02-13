import requests
import dihlibs.functions as fn
from dihlibs.node import Node
import json
from functools import wraps


class SupersetAPI:
    def __init__(self, rc, file=".secret.yml"):
        self.file = file
        self.rc = rc
        self.session = requests.Session()
        self.is_authenticated = False
        self.url = None

    def login(self):
        """Logs in to Superset and starts a session."""
        cred = Node(fn.load_file_data(self.file)).get(self.rc)
        self.url = cred.get("url").strip('/')
        payload = {"username": cred.get("username"), "password": cred.get("password")}
        response = self.session.post(self.url + "/login", json=payload)
        self.is_authenticated = response.status_code == 200
        return self.is_authenticated

    def ensure_authenticated(self):
        """Ensures the session is authenticated before making requests."""
        if not self.is_authenticated or not self.url:
            return self.login()
        return True

    def retry_on_auth_failure(func):
        """Decorator to handle session expiration and retry authentication."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self.ensure_authenticated()
            response = func(self, *args, **kwargs)
            if response.status_code in [401, 403]:  # Session expired
                if self.login():  # Re-login and retry
                    response = func(self, *args, **kwargs)
            return response

        return wrapper

    
    @retry_on_auth_failure
    def post(self,url,*args,**kwargs):
        print(url)
        return self.session.post(self.url+url,*args,**kwargs)

    @retry_on_auth_failure
    def get(self,url,*args,**kwargs):
        print(url)
        return self.session.get(self.url+url,*args,**kwargs)

    def list_dashboards(self):
        """Fetches a list of dashboards."""
        dashboard_list_url = f"/api/v1/dashboard/"
        return self.get(dashboard_list_url)

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
        files = {"formData": ("dashboard.zip", open(import_file, "rb"), "application/zip")}
        passwords={f"databases/{k}.yaml": v for k, v in passwords.items()}
        data = {
            "passwords": json.dumps(passwords),
            "overwrite": "true",
        }
        return self.post(url, files=files, data=data)

    def copy_dashboard(self, from_sa, dashboard_ids, passwords={}):
        res = from_sa.export_dashboards( dashboard_ids, export_filename="cp_dashboards.zip")
        if res.status_code == 200:
            return self.import_dashboards(
                import_file="cp_dashboards.zip", passwords=passwords
            )
