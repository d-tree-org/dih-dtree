# from __future__ import print_function
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
import httplib2
import io
import pandas as pd

class Drive:
    def __init__(self, key: dict):
        try:
            scope = [
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(key, scope)
            http = httplib2.Http(timeout=30)
            self.drive = build("drive", "v3", credentials=credentials)
        except Exception as e:
            print(e)

    def _exists(self, it):
        return it is not None

    def _is_folder(self, item):
        return item["mimeType"] == "application/vnd.google-apps.folder"

    def get_files_in_folder(self, folder_id):
        try:
            res = {"id": folder_id}
            res["files"] = (
                self.drive.files()
                .list(
                    q=f"parents in '{folder_id}'",
                    fields="files(id, name, mimeType,parents)",
                )
                .execute()
                .get("files", res)
            )
            if res["files"] is None:
                return None
            for f in filter(self._is_folder, res["files"]):
                f["files"] = self.get_files_in_folder(f["id"])["files"]
            return res
        except HttpError as error:
            print(f"An error occurred: {error}")

    def upload_excel_file(self, file_name, to_folder_id):
        try:
            file_metadata = {
                "parents": [to_folder_id],
                "name": file_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
            }
            media = MediaFileUpload(file_name, resumable=True)
            file = (
                self.drive.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            return file.get("id")
        except HttpError as error:
            print(f"An error occurred: {error}")

    def download(self, request):
        try:
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                _, done = downloader.next_chunk(num_retries=5)
                print('.',end='')
            file.seek(0)
            return file.getvalue()
        except HttpError as error:
            print(f"An error occurred: {error}")
            file = None

    def download_excel_file(self, file_id):
        request = self.drive.files().export_media(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        return self.download(request)

    def download_file(self, file_id):
        request = self.drive.files().get_media(fileId=file_id)
        return self.download(request)

    def get_df(self,file,sheet_name):
       return pd.read_excel(self.download_excel_file(file),sheet_name)
