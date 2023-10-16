## Cronies
This is designed to efficiently manage various cron jobs, segmented by their generic types (e.g., dhis2) and further by specific project implementations. This modular structure allows for the easy addition, modification, or removal of cron jobs while ensuring shared resources are centrally managed.

 The central component is the script defined in the file `run`, which is primaliry meant to be invoked by a cron job. This script is not just a typical executable but also contains metadata in the form of comments that indicate environment setup prerequisites. These comments act as a "self-documentation" mechanism, making it easier for automated scripts or developers to understand the required setup for execution.

#### Project Structure
The project is organized into different levels:

- First Level: Represents the generic type of the cron job (e.g., dhis2). It can also contain common shared resources for various implementations.
- Second Level: Specific implementations for different projects. Each of these folders generally contains a run file with instructions and the actual code to be executed.
```
   └── cronies/
    ├── dhis/
    │   ├── cron1/
    │   │   ├── run
    │   │   └── sql/
    │   ├── cron2/
    │   │   ├── run
    │   │   └── sql/
    │   ├── src/
    │   │   
    │   ├── templates/
    ├── libs/
    │   
    └── sms/
        └── jna/
            └── src/
```

#### DHIS2
DHIS2 cron jobs focus on [Brief description of DHIS2 cron jobs].
- Dev  
  Purpose: [Describe what this specific cron job does, its significance, and output.]

#### Common Libraries (libs/)
This directory contains libraries and modules shared across various cron jobs in the project.

#### Sample run file
Below is a sample of a run file which defines an entry point of execution by a cron job

```
#!/usr/bin/env python
# apt-get install libbz2-dev ssh-client postgresql-client
# pip install --upgrade pandas openpyxl SQLAlchemy psycopg2-binary google-api-python-client google-auth-httplib2 google-auth-oauthlib oauth2client
# cron_time 03 03 10 * *
import sys,argparse
sys.path.extend(["../../libs",'../src'])

import main 
import utils as fn


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Script for pushing data from data warehouse to dhis2')
    parser.add_argument('-m', '--month', type=str, help='Date in format YYYY-MM')
    parser.add_argument('-n', '--only-new', action='store_true', help='Flag for new elements only')
    args = vars(parser.parse_args())  # Convert args to dictionary

    data=main.start(
        month=fn.parse_month(args['month']) if args.get('month') else fn.get_month(-1),
        task_name="dhis-jna",
        only_new_elements=args.get('only_new')
    )

```


##### Run file components
- **Script Invocation (#!/usr/bin/env python):**
    - The shebang line indicates the interpreter's path for executing the script, denoting that it's a Python script.
- **Environment Setup Comments:**
    - These are metadata indicating environment prerequisites.  
    - The commands starting with # are not executed as part of the Python script but can be parsed by a helper script.
    - Examples:
        - System package installations using apt-get.
        - Python library installations using pip.
        - Cron scheduling information.

- **Script Execution:**
    - Python imports and other configuration setups.
    - Logic for the main execution, using condition checks, arguments parsing, etc.  

#### Workflow
- Environment Setup:
    Before the run script is invoked by a cron job, a helper script can parse the comments in the run script to ensure the environment is appropriately set up.  
    This includes installing necessary system packages, Python libraries, and setting the correct cron timing.

- Cron Job Invocation:
    The cron job scheduler invokes the run script based on the specified schedule.  
    The example provided uses the given Python interpreter to execute. However any script environment can be used, eg. nodejs, java etc, provided it can be invoked by ./run in a linux docker container environment.  

#### Benefits
- Self-contained: Each run script acts as a self-contained module, encapsulating both the logic and the environment prerequisites.
- Scalable: New cron jobs can be added as separate run scripts, each with its own environment prerequisites.
- Maintainable: Changes to the environment or logic can be made directly within the respective run script, ensuring clarity and traceability.



#### Setup & Installation
- Clone the repository: git clone [repository_link]
- Create a project folder and cron subfolder inside it
- Create a run file inside the cron subfolder as an entry point to your code to be run as a crone
- If docker container dih-cronies is not running, start it by `dih docker-compose.yml` or by running `docker-compose up -d`
- Run `dih add <project_folder>.<cron_folder>`