## Command line helper script: dih  
#### Script Description
This Bash script is designed to perform various tasks related to a project. It includes functions for managing Docker containers, generating Docker Compose configuration files, copying configuration files, and more.

#### Prerequisites
Before using this script, ensure you have the following prerequisites:

- Docker installed on your system.


### Installation

To make this script available as a command with a name starting with "dih" follow one of these methods:

- **Create a Bash Alias:**
    - In your .bashrc add a line
        ```
        alias dih=<path_project>/.bin/dih
        ```
- **OR Create a Symbolic link**
    - Run the following command
        ```
        ln -s <path_to_project>/.bin/dih /usr/local/bin/dih
        ```

### Usage

- To generate Compose File from JSON Configuration
    - Generate a Docker Compose file from a JSON configuration file. Replace your_config.json with the path to your JSON configuration file:
        ```
        dih your_config.json
        ```

- Start Docker Containers
    - To start Docker containers using a Docker Compose file (YAML), replace your_compose.yml with the path to your Docker Compose file:
        ```
        dih your_compose.yml
        ```

- View Container Logs
    - To view container logs, specify the Docker Compose file and the service name:
        ```
        dih logs your_compose.yml service_name ```

- To mannually run cron defined inside a Docker container. Replace cron-name with the name of the cron, and provide the desired command:
    - To run for previous month only 
        ```
        dih run <cron-name>  
        ```
    - To run for  any month 
        ```
        dih run <cron-name> --month yyyy-mm
        ```
    - To run for  any month but only with new elements (helpful when you only want to push historical data for new element)
        ```
        dih run <cron-name> -m yyyy-mm --new-only 
        ```

- #### Container and resources management
    - Create shared Docker resources, including a Docker network and volume:
        ```
        dih common
        ```

    - To stop Docker containers based on a name pattern in container name:
        ```
        dih stop <keyword in container-name>
        ```

    - Stop and remove Docker containers based on a name pattern in container name:
        ```
        dih rm <keyword in container-name>
        ```

    - To stop and remove all Docker containers and volumes ***EVEN THOSE FROM OTHER PROJECTS***, execute the following command:
        ```
        dih clear
        ```

Configuration
...

License
This script is licensed under the MIT License - see the LICENSE file for details.

Acknowledgments
...