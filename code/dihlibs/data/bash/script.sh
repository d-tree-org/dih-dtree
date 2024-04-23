#!/bin/bash

function trim() { sed -r 's/^\s*//g;s/\s*$//g'; }
function quiet() { "$@" &>/dev/null; }
function quote() {
    read -r a
    printf '%s\n' "$a" | sed 's:[\/&]:\\&:g'
}

function get_nth_dir() {
    local p="$1"
    for ((i = 0; i < $2; i++)); do p=$(dirname "$p"); done

    local dir_name=$(basename "$p")
    echo "$dir_name" "$p"
}

function encrypt() {
    # Check for password input method
    echo "Enter password for encryption:"
    read -s password
    echo # Move to a new line for cleaner output

    if [ "$#" -ne 1 ]; then
        echo You must specify the file to encrypt
        return 1
    fi

    local file="${1%/}"
    local encrypt="$file.zip"
    quiet zip -r "$encrypt" "$file"
    # File name is provided, encrypt the file
    openssl enc -aes-256-cbc -pbkdf2 -iter 10000 -salt -in "$encrypt" -out "$encrypt.enc" -pass pass:"$password"
    [ "$?" -eq 0 ] && rm -rf "$file"
    rm "$encrypt"
}

function decrypt() {
    echo "Enter password for decryption:"
    read -s password
    echo # Move to a new line for cleaner output

    if [ "$#" -eq 1 ]; then
        local encrypted_file="$1"
        local file="${encrypted_file%.enc}"
        openssl enc -aes-256-cbc -d -pbkdf2 -iter 10000 -salt -in "$encrypted_file" -out "$file" -pass pass:"$password"
        [[ "$?" -ne 0 ]] && rm -rf "$file" && return 1
        [[ $file =~ \.zip$ ]] && quiet unzip "$file" && rm "$file" "$file.enc"
    fi
}

function strong_password() {
    length=$([[ $1 =~ ^[0-9]*$ ]] && echo $1 || echo 64)
    trim <<-CODE | python
    import dihlibs.functions as fn
    print(fn.strong_password($length))
CODE
}

function turn_on_cron_container() {
    create_shared_docker_resources
    docker-compose -f .cache/docker/cronies/docker-compose.yml up -d 2>&1
}

function turn_on_dhis_containers() {
    create_shared_docker_resources
    docker-compose -f .cache/docker/backend/dhis/"$1"-compose.yml up -d 2>&1
}

function set_cron() {
    read proj path <<<$(get_nth_dir "$1" 1)
    file="$(basename "$1")"
    conf="${file%.zip.enc}/config.yaml"
    user="$(yq .dih_user -r <"$conf")"
    cron="$(yq .cronies.cron_time -r <$conf) run ${proj} ${file}"

    docker exec -u $user dih-cronies bash -c 'crontab -l | {
        read cronies;
        echo "$cronies" | sed "s/#.*//g"|grep -vE "^\W*$" | grep -Eq "(PATH|SHELL)" || echo -e "SHELL=/bin/bash\\nPATH=$PATH"
        echo "$cronies" | grep -Eq "'"$cron"'" || echo -e "$cronies"\\n"'"$cron"'" ;
    } | crontab -'
    echo "done setting cron"
}

function create_docker_user() {
    folder="$(basename ${1%.zip.enc})"
    user="$(yq .dih_user -r <"$folder"/config.yaml)"

    docker exec -i dih-cronies bash -c "
        id -u $user &> /dev/null ||
        useradd -m -s /bin/bash -g dih $user &> /dev/null
        chown -R $user /dih/cronies/$2"
}

function files_to_container() {
    folder="$(basename ${1%.zip.enc})"
    read proj path <<<$(get_nth_dir "$1" 1)

    rename_host='s/(dhis_url.*)localhost([^@]*$)?/\1'"${folder}"'-dhis:8080\2/g'
    sed -ri "$rename_host" "$folder/config.yaml"

    strong_password >.env
    docker exec dih-cronies mkdir -p "/dih/cronies/${proj}"
    for x in {.cache,sql,"$folder",.env}; do
        docker cp ./$x "dih-cronies:/dih/cronies/${proj}"
    done
    docker exec dih-cronies bash -c '( cd /dih/cronies/'"$proj"' && dih -a encrypt '"$folder"' < .env)'

}

function deploy_cron() {
    file="$(realpath $1)"
    read locname loc <<<$(get_nth_dir "$file" 1)

    temp=$(mktemp -d)
    cp -r "$loc/"* "$loc"/.[!.]* "$temp"
    cd $temp
    [ -d "$file" ] || decrypt $(basename "$file") <.env
    files_to_container "$file"
    create_docker_user "$file"
    set_cron "$file"
    rm -rf $temp

    [ -d "$file" ] && strong_password 65 >.env && encrypt $file <.env
    echo done deployment of "$proj"
}

function nuke-docker(){
    docker container ls -aq | xargs docker stop | xargs docker rm
    docker images -q | xargs docker image rm
    yes | docker image prune
    docker network ls -q| xargs docker network rm
    docker volume ls -q| xargs docker volume rm
}

function perform() {
    case $1 in
    deploy) deploy_cron $2 ;;
    encrypt) encrypt $2 ;;
    decrypt) decrypt $2 ;;
    password) strong_password $2 ;;
    dhis-log*) docker-compose -f .cache/docker/backend/dhis/"${2%.zip.enc}"-compose.yml logs -f ;;
    cron-log*) docker-compose -f .cache/docker/cronies/docker-compose.yml logs -f ;;
    down) docker-compose -f $2 down ;;
    stop) docker ps | grep "$2" | awk '{print $1}' | xargs docker stop ;;
    rm) docker container ls -a | grep "$2" | awk '{print $1}' | xargs docker stop | xargs docker rm ;;
    nuke-docker) nuke-docker ;;
    esac
}

function create_shared_docker_resources() {
    quiet docker network inspect dih-network ||
        docker network create --subnet=172.10.16.0/24 dih-network

    quiet docker volume inspect dih-common ||
        docker volume create dih-common
}

function check_if_docker_needs_sudo() {
    quiet command -v docker ||
        alias docker='sudo docker'
    quiet command -v docker-compose ||
        alias docker-compose='sudo docker-compose'
}

check_if_docker_needs_sudo
