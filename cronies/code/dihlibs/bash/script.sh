#!/bin/bash

function trim() { sed -r 's/^\s*//g;s/\s*$//g'; }
function quiet() { "$@" &>/dev/null; }

function encrypt() {
    echo "Enter password for encryption:"
    read -s password
    echo # Move to a new line for cleaner output
    if [ "$#" -eq 1 ]; then
        file="${1%/}"

        if [ -d $file ]; then
            zipped="${file}.zip"
            quiet zip -r "$zipped" "$file"
        fi
        # File name is provided, encrypt the file
        openssl enc -aes-256-cbc -pbkdf2 -iter 10000 -salt -in "$zipped" -out "$zipped.enc" -pass pass:"$password"
        [ -d "$file" ] && rm -rf "$zipped" "$file"
    else
        openssl enc -aes-256-cbc -pbkdf2 -iter 10000 -salt -pass pass:"$password"
    fi
}

function decrypt() {
    echo "Enter password for decryption:"
    read -s password
    echo # Move to a new line for cleaner output

    if [ "$#" -eq 1 ]; then
        local encrypted_file="$1"
        local file="${encrypted_file%*.enc}"
        openssl enc -aes-256-cbc -d -pbkdf2 -iter 10000 -salt -in "$encrypted_file" -out "$file" -pass pass:"$password"
        [[ $file =~ \.zip$ ]] && unzip "$file" && rm "$file" #"$file.enc"

    else
        # No file name provided, read from stdin and decrypt
        echo # still need to work on decrypting from stdin
        # cat | openssl enc -aes-256-cbc -d -pbkdf2 -iter 10000 -salt -pass pass:"$password"
    fi
}

function deploy_cron() {
    file="${1%/}"
    folder="${file%.zip.enc}"
    [ -d "$file" ] || decrypt "$file" <.env
    user="$(yq .user -r <"$folder"/config.yaml)"
    cron_time="$(yq .cron_time -r <"$folder"/config.yaml)"
    encrypt "$folder" <.env
    proj=$(dirname .env)

    docker cp "${proj}" dih-cronies:/dih/cronies/
    cmd="$cron_time ( cd /dih/cronies/${proj} && dih )"
    docker exec -it dih-cronies bash -c "id -u $user &>/dev/null || useradd -m -s /bin/bash $user"
    docker exec -u $user dih-cronies bash -c "{crontab -l ; $cmd  } | crontab - "
    echo done deployment of $proj
}

# function remove_cron() {
#     file="${1%/}"
#     folder="${file%.zip.enc}"
#     [ -d "$file" ] || decrypt "$file" <.env
#     user="$(yq .user -r <"$folder"/config.yaml)"
#     cron_time="$(yq .cron_time -r <"$folder"/config.yaml)"
#     encrypt "$folder" <.env
#     proj=$(dirname .env)

#     docker exec -u "$user" dih-cronies bash -c 'crontab -l | grep -vE "\b'"$1"'\$" | crontab -' &&
#         docker exec dih-cronies rm -r "$folder"
# }
