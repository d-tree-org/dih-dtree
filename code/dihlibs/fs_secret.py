import os
import secrets, string
import hashlib
import sqlite3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pathlib import Path


CONFIG_DIR = f'{ Path.home() }/.config/dihlibs/'
DEFAULT_SALT_FILE = f'{ Path.home() }/.config/dihlibs/.salt'
DEFAULT_CONFIG_DB = f'{ Path.home() }/.config/dihlibs/config.db'

_CREATE_TABLE = """ 
CREATE TABLE IF NOT EXISTS encrypted_files (
    H_filename BLOB PRIMARY KEY,
    H_content BLOB,
    nonce BLOB,
    ciphertext BLOB
) """
_OVERWITE_SECRET = """ DELETE FROM encrypted_files WHERE H_filename = ?  """
_INSERT_SECRET = """
    INSERT INTO encrypted_files (H_filename, H_content, nonce, ciphertext)
    VALUES (?, ?, ?, ?)
    ON CONFLICT DO NOTHING
"""
def _remove_secret_file(filename):
    if os.path.exists(filename):  # Check if file exists before deleting
        os.remove(filename)
        print("Secret file deleted successfully since it is no longer needed")
    else:
        print("File not found")

def _count_rows(db):
    cursor=db.execute("SELECT COUNT(*) FROM encrypted_files")
    return cursor.fetchone()[0]

def _get_salt(file_path):

    if os.path.isfile(file_path):
        with open(file_path, "r") as salt:
            return salt.read()

    elif file_path == DEFAULT_SALT_FILE:
        os.makedirs(CONFIG_DIR,exist_ok=True)
        characters = string.ascii_letters + string.digits + string.punctuation
        password = "".join(secrets.choice(characters) for _ in range(32))
        with open(DEFAULT_SALT_FILE, "w") as salt_file:
            salt_file.write(password)
            return password
    else:
        raise ValueError("the path provided does not exists")


def encrypt_secret(
    secret_path: str,
    overwite=False,
    salt_file_path = DEFAULT_SALT_FILE,
    storage = DEFAULT_CONFIG_DB,
) -> None:

    with open(secret_path, "rb") as file:
        file_content = file.read()
    
    filename=os.path.basename(secret_path)

    secret_salt = _get_salt(salt_file_path)
    H_content = hashlib.sha256(file_content).digest()
    H_filename = hashlib.sha256(filename.encode("utf-8")).digest()

    key_input = H_content + filename.encode("utf-8") + secret_salt.encode('utf-8')
    key = hashlib.sha256(key_input).digest()

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 12 bytes is standard for GCM
    ciphertext = aesgcm.encrypt(nonce, file_content, associated_data=H_filename)

    db = sqlite3.connect(storage)
    db.execute(_CREATE_TABLE)
    if overwite:
        db.execute(_OVERWITE_SECRET,(H_filename,))

    before=_count_rows(db)
    db.execute(_INSERT_SECRET, (H_filename, H_content, nonce, ciphertext))
    affected=_count_rows(db) - before
    if affected > 0:
        _remove_secret_file(secret_path)
    db.commit()


def decrypt_secret(
    secret_path: str,
    salt_key_file=DEFAULT_SALT_FILE,
    key_storage=DEFAULT_CONFIG_DB,
) -> bytes:

    secret_path=os.path.basename(secret_path)
    with open(salt_key_file, "rb") as sec:
        secret_salt = sec.read()
    H_filename = hashlib.sha256(secret_path.encode("utf-8")).digest()

    db = sqlite3.connect(key_storage)
    cursor = db.execute( " SELECT H_content, nonce, ciphertext FROM encrypted_files WHERE H_filename=?" ,(H_filename,))

    if (row := cursor.fetchone()) is None:
        raise ValueError("File not found")

    H_content, nonce, ciphertext = row
    key_input = H_content + secret_path.encode("utf-8") + secret_salt
    key = hashlib.sha256(key_input).digest()

    aesgcm = AESGCM(key)
    try:
        decrypted = aesgcm.decrypt(nonce, ciphertext, associated_data=H_filename)
    except Exception as e:
        raise ValueError("Decryption failed") from e

    # Verify integrity
    if hashlib.sha256(decrypted).digest() != H_content:
        raise ValueError("Integrity check failed")
    return decrypted
