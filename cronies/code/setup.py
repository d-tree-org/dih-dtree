from setuptools import setup, find_packages

setup(
    name="dihlibs",
    version="0.0.5",
    author="Nitu",
    author_email="nkataraia@d-tree.org",
    description="A helper package for data integrations",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/nKataraia/dihlibs",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "asyncio",
        "requests",
        "pandas",
        "openpyxl",
        "SQLAlchemy",
        "psycopg2-binary",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "oauth2client",
    ],
    entry_points={
        "console_scripts": [
            "dih = dihlibs.dhis.main:start",  # Specify the path to your Bash script here
        ]
    },
)
