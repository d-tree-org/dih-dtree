### Script Usage:

This script provides a set of commands for managing various tasks related to deployment, encryption, decryption, Docker container management, and logging.

#### Commands:

##### deploy
Deploy a cron job or task.
Syntax: dih -a deploy [cron_file]
[cron_file]: Path to the cron file to be deployed.

##### encrypt
Encrypt a file.
Syntax: dih -a encrypt [file]
[file]: Path to the file to be encrypted.

##### decrypt
Decrypt a file.
Syntax: dih -a decrypt [file]
[file]: Path to the file to be decrypted.

##### logs
View logs of Docker containers.
Syntax: dih -a logs [compose_file]
[compose_file]: Path to the Docker Compose file.

##### down
Stop and remove containers, networks, volumes, and images created by up.
Syntax: dih -a down [compose_file]
[compose_file]: Path to the Docker Compose file.

##### stop
Stop a specific Docker container.
Syntax: dih -a stop [container_name]
[container_name]: Name of the Docker container to be stopped.

##### rm
Stop and remove containers.
Syntax: dih -a rm
This command will stop and remove all Docker containers.