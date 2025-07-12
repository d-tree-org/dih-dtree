from setuptools import setup, find_packages

setup(
    name="dihlibs",
    version="0.0.79",
    author="Nitu",
    author_email="nkataraia@d-tree.org",
    description="A helper package for data integrations",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/nKataraia/dihlibs",
    packages=find_packages(),
    package_data={
        # If any package contains non-Python files, include them here
        "dihlibs": [
            "data/bash/script.sh",
            "data/describe_table.sql",
            "data/df_update_table.sql",
            "data/docker/backend.zip",
            "data/docker/cronies.zip",
            "data/dhis_templates/category_options.json",
            "data/dhis_templates/data_element.json",
            "data/dhis_templates/data_set.json"
        ],
    },
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
        "pyjwt",
        "google-api-python-client",
        "google-auth-oauthlib",
        # "oauth2client", #deprecated
        "google-auth",
        "aiohttp",
        "pyyaml",
        "fuzzywuzzy",
        "setuptools",
        "python-Levenshtein",
        "cryptography",
    ],
    entry_points={
        "console_scripts": [
            "dih = dihlibs.dhis.main:start",  # Specify the path to your Bash script here
        ]
    },
)
