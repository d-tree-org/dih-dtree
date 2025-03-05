# from __future__ import print_function
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
import io
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build


class Drive:
    def __init__(self, key: dict = None, credentials=None):
        try:
            scopes = [
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
            if credentials is None:
                if key is not None:
                    credentials = service_account.Credentials.from_service_account_info(key, scopes=scopes)
                else:
                    raise ValueError("Either 'key' or 'credentials' must be provided.")
            self.drive = build("drive", "v3", credentials=credentials)
        except Exception as e:
            print(e)


    def get_files_in_folder(self, folder_id):
        folder = {
            "id": folder_id,
            "files": self.drive.files().list(
                q=f"parents in '{folder_id}'",
                fields="files(id, name, mimeType,parents)",
            ),
        }
        folder_only = (
            lambda x: x.get("mimeType") == "application/vnd.google-apps.folder",
        )
        for f in filter(folder.get("files"), folder_only):
            f["files"] = self.get_files_in_folder(f["id"])
        return folder

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
            file.seek(0)
            return file
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

    def get_df(self, file, sheet_name):
        return pd.read_excel(self.download_excel_file(file), sheet_name)

    def get_excel(self, fileid):
        return pd.ExcelFile(self.download_excel_file(fileid))