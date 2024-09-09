#!/bin/bash

source <(printenv | grep -v LS_COROR)

function trim() { sed -r 's/^\s*//g;s/\s*$//g'; }
function quiet() { "$@" &>/dev/null; }

function install_apt_dependencies() {
    echo 'installing apt dependencies'
    regx='^\W*#\W*apt(-get)?\s*\K.*'
    files=$(find /dih/cronies -maxdepth 3 -name run -type f -exec grep -lP $regx {} '+' | xargs)
    [ -z "$files" ] && return
    grep -ohP $regx $files |
        sed -r 's/(install|update)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u | xargs apt-get install -y
    chmod ug+x $files
    [ -n $files ] && sed -i '/^\W+apt\W.*/d' $files
}

function setup_user() {
    echo 'setting up user'
    for key in {proj,user,domain_name,http_port,https_port}; do
        grep -rFl "\${$key}" /dih | xargs sed -ri "s/\\$\{$key\}/${!key}/g"
    done

    quiet id doe && return 0;
    if [ -n doe ] && [ ! -f /home/doe ]; then
        useradd -m -g dih doe
        chmod o-wxr -R /dih && chown -R :dih /dih
        chown -R doe /home/doe
        runuser -u doe -- mkdir /home/doe/.bin
        [ ! -f /dih/common/certs/ssh/id_rsa ] && {
            ssh-keygen -t rsa -f /dih/common/certs/ssh/id_rsa -N ""
            cat /dih/common/certs/ssh/id_rsa.pub
        }
        ln -s /dih/common/certs/ssh /home/doe/.ssh
    fi
}

function setup_python() {
    if which python >/dev/null; then return 0; fi
    here="$PWD"
    cd /dih/lib
    # url="https://storage.googleapis.com/py-binary/python-3.11.3.tar.xz"; 
    url='https://storage.googleapis.com/jamii-ni-afya-1591691553498.appspot.com/python-3.11.3.tar.xz'
    wget --no-check-certificate -O /dih/lib/python-3.11.3.tar.xz --progress=dot:giga "$url";
    tar -xJf /dih/lib/python*.xz
    ln -s /dih/lib/python/bin/python3 /dih/bin/python
    ln -s /dih/lib/python/bin/pip3 /dih/bin/pip
    chmod g+w  -R /dih/lib/python
    cd "$here"
}

function install_pip_dependencies() {
    regx='^\W*#\W*pip\s*\K.*'
    files=$(find /dih/cronies -name run -maxdepth 3 -type f -exec grep -lP $regx {} '+' | xargs)
    grep -ohP $regx $files |
        sed -r 's/(install|\-\-upgrade)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u |
        xargs pip install --upgrade pip
        pip install dihlibs
    [ -n "$files" ]  && sed -ri 's/^\W*#\W*pip\W.*//g' "$files"
    echo 'done installing pip dependencies'
}

function set_logfile(){
    mkdir -p /dih/cronies/logs
    touch /dih/cronies/logs/cron.log
    chmod g+w /dih/cronies/logs/cron.log
}



function should_initialize() {
    ! quiet crontab -l &&
        ! quiet which python &&
        ! quiet which pip
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
    trim <<-CODE | python
    import dihlibs.functions as fn
    print(fn.strong_password($1))
CODE
}