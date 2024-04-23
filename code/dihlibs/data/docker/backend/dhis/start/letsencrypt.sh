#!/bin/bash

source common.sh


function notify_nginx() {
    echo $1 | nc -q 2 localhost 12345
}

function setup_python() {
    quiet python --version && return
    echo setting up python
    here=$(pwd) && mkdir -p /dih/lib;
    cd /dih/lib
    url="https://storage.googleapis.com/py-binary/python-3.11.3.tar.xz"; 
    wget --no-check-certificate -O /dih/lib/python-3.11.3.tar.xz --progress=dot:giga "$url"
    quiet tar -xf python*xz
    ln -s /dih/lib/python/bin/pip3 /dih/bin/pip &&
        ln -s /dih/lib/python/bin/python3 /dih/bin/python
    echo setting up python $(pwd)
    cd $here
}

certs_dir="/dih/common/certs/letsencrypt"
function setup_certbot() {
    setup_python
    quiet pip show certbot && quiet crontab -l && echo "certbot is already installed" && return; 
    pip install --upgrade pip certbot || { echo 'failed to install certbot' && return; }
    mkdir -p $certs_dir/{logs,config,work,log}
    chmod -R 755 $certs_dir
    touch $certs_dir/logs/cron.log

    current_time=$(date -d "+2 minutes" "+%M %H")
    next_hour=$(date -d "+12 hours" "+%H")

    echo "$user setting $current_time $nexthour cron hapa"
    echo -e "SHELL='/bin/bash'
        PATH='$PATH'
        domain_name='$domain_name'
        $current_time,$next_hour * * * renew &>> $certs_dir/logs/cron.log " | trim | crontab - &&
            echo 'successfully installed certbort cron' ||
            {
                echo 'failed to install certbot cron'
                return 1
            }
}

function not_valid_domain() {
    [ -z "$domain_name" ] &&
        { echo "Domain name is empty. Please provide a valid domain name."; return 0; }

    grep -Pq '^(?!.*(?:local|example))[\w_\.\-]+$' <<<"$domain_name" ||
        { echo "Domain name '$domain_name' is not valid, so not starting Let's Encrypt."; return 0; }

    return 1
}


function is_renewed() {
    certbot --standalone --text --agree-tos \
        --server https://acme-v02.api.letsencrypt.org/directory \
        --rsa-key-size 4096 --verbose --keep-until-expiring \
        --register-unsafely-without-email \
        --preferred-challenges http \
        --config-dir $certs_dir/config \
        --work-dir $certs_dir/work \
        --logs-dir $certs_dir/logs \
        -d ${domain_name} \
        certificates | if grep -qE '(Renewal Date|No certificates found)'; then return 12; fi
}

function renew() {
    not_valid_domain && return 0;
    is_renewed && echo 'Certificates are up to date no need to renew' || {
        notify_nginx 'renewing_certs' &&
            certbot certonly --standalone --text --agree-tos \
                --server https://acme-v02.api.letsencrypt.org/directory \
                --rsa-key-size 4096 --verbose --keep-until-expiring \
                --register-unsafely-without-email \
                --http-01-port 7000 \
                --preferred-challenges http \
                --config-dir $certs_dir/config \
                --work-dir $certs_dir/work \
                --logs-dir $certs_dir/logs \
                -d ${domain_name} &&
            notify_nginx "reload"
    }
}

setup_certbot && renew
