#!/bin/bash
source <(printenv | grep -v LS_COROR)

function trim() { sed -r 's/^\s*//g;s/\s*$//g'; }
function quiet() { "$@" &>/dev/null; }
function create_run_command() {
    echo 'creating a cron runner'
    cat <<-RUN_FILE | sed -r 's/^\s+//g' >/dih/bin/run &&
        #!/bin/bash
        $(printenv | sed -r '/[A-Z]+=/d;s/^./export \0/')
        cd /dih/cronies/\${1//./\//}
        echo running \$1 >> /dih/cronies/logs/cron.log  2>&1
        ./run "\${@:2}" >> /dih/cronies/logs/cron.log  2>&1
RUN_FILE
        chmod +x /dih/bin/run && chown :dih /dih/bin/run
    echo user set
}

function install_apt_dependencies() {
    echo 'installing apt dependencies'
    regx='^\W*#\W*apt(-get)?\s*\K.*'
    files=$(find /dih/cronies -maxdepth 3 -name run -type f -exec grep -lP $regx {} '+' | xargs)
    [ -z "$files" ] && return
    grep -ohP $regx $files |
        sed -r 's/(install|update)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u | xargs apt-get install -y
    chmod ug+x $files
    sed -i '/^\W+apt\W.*/d' $files
}

function setup_user() {
    echo 'setting up user'
    for key in {proj,user,domain_name,http_port,https_port}; do
        grep -rFl "\${$key}" /dih | xargs sed -ri "s/\\$\{$key\}/${!key}/g"
    done

    quiet id $dih_user && return 0;
    if [ -n $dih_user ] && [ ! -f /home/$dih_user ]; then
        useradd -m -g dih $dih_user
        chmod o-wxr -R /dih && chown -R :dih /dih
        chown -R $dih_user:dih /home/$dih_user
        runuser -u $dih_user -- mkdir /home/$dih_user/.bin
        [ ! -f /dih/common/certs/ssh/id_rsa ] && {
            ssh-keygen -t rsa -f /dih/common/certs/ssh/id_rsa -N ""
            cat /dih/common/certs/ssh/id_rsa.pub
        }
        ln -s /dih/common/certs/ssh /home/$dih_user/.ssh
    fi
}

function setup_python() {
    if which python >/dev/null; then return 0; fi
    cd /dih/lib
    tar -xJf /dih/lib/python*.xz
    ln -s /dih/lib/python/bin/python3 /dih/bin/python
    ln -s /dih/lib/python/bin/pip3 /dih/bin/pip
}

function install_pip_dependencies() {
    pip --version
    regx='^\W*#\W*pip\s*\K.*'
    files=$(find /dih/cronies -name run -maxdepth 3 -type f -exec grep -lP $regx {} '+' | xargs)
    grep -ohP $regx $files |
        sed -r 's/(install|\-\-upgrade)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u |
        xargs pip install --upgrade pip
    sed -ri 's/^\W*#\W*pip\W.*//g' $files
}

function install_cron() {
    mkdir -p /dih/cronies/logs
    touch /dih/cronies/logs/cron.log
    regx='^\W*#\W*cron_time\s*\K.*'
    files=$(find /dih/cronies -name run -maxdepth 3 -type f -exec grep -lP $regx {} '+' | xargs)
    {
        echo -e "SHELL=/bin/bash\nPATH=$PATH"
        grep -HoP $regx $files |
            while IFS=':' read -r script cron; do
                cmd=$(sed -E 's|/+|.|g;s|.+cronies.(.+).run|\1|g' <<<$script)
                echo "$cron run $cmd"
            done
    } | crontab -
    sed -ri 's/^\W*#\W*cron_time\W.*//g' $files
}


function should_initialize() {
    ! quiet crontab -l &&
        ! quiet which python &&
        ! quiet which pip
}


function encrypt(){
  local password="$1"
  local file_to_encrypt="$2"
  local encrypted_file="${file_to_encrypt}.enc"
  openssl enc -aes-256-cbc -pbkdf2 -iter 10000 -salt -in "$file_to_encrypt" -out "$encrypted_file" -pass pass:"$password"
}


function decrypt(){
  local password="$1"
  local encrypted_file="$2"
  local file="${encrypted_file%*.enc}"
  openssl enc -aes-256-cbc -d -pbkdf2 -iter 10000 -salt -in "$encrypted_file" -out "$file" -pass pass:"$password"
}
