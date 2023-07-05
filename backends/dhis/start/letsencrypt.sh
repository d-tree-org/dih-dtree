#!/bin/bash 

source common.sh

function notify_nginx(){
    echo $1 | nc -q 2 localhost 12345
}


function setup_python(){
    quiet python --version && return;
    echo setting up python
    here=$(pwd) && cd /dih/lib
    quiet tar -xvf python*xz 
    ln -s /dih/lib/python/bin/pip3 /dih/bin/pip \
       && ln -s /dih/lib/python/bin/python3 /dih/bin/python
    echo setting up python $(pwd)
    cd $here;
}

certs_dir="/dih/common/certs/letsencrypt"
function setup_certbot(){
    setup_python
    quiet pip show certbot >> /dev/null && crontab -l >>/dev/null && return  # certbot is already installed returning
    pip install --upgrade pip certbot || { echo 'failed to install certbot' && return; }
    echo 'creating folders'
    mkdir -p $certs_dir/{logs,config,work,log}
    chmod -R 755 $certs_dir
    touch $certs_dir/logs/cron.log
    echo "1 */12 * * * renew >> $certs_dir/logs/cron.log 2>& " | crontab - || { echo 'failed to install cron';return 12; }
}

function not_valid_domain(){
    (grep -qE "(example.\w+|.*.local|^[^.]*$)" <<< $domain_name ||  [ -z $domain_name ]) \
    && echo "Domain name ${domain_name} is not a valid domain, so not starting letsencrypt" 
}

function is_renewed() {
  certbot  --standalone --text  --agree-tos \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --rsa-key-size 4096 --verbose --keep-until-expiring \
    --register-unsafely-without-email \
    --preferred-challenges http \
    --config-dir $certs_dir/config \
    --work-dir $certs_dir/work \
    --logs-dir $certs_dir/logs \
    -d ${domain_name}  \
    certificates | if grep -qE '(Renewal Date|No certificates found)'; then return 12; fi
}

function renew(){
    not_valid_domain && return
    is_renewed && echo 'Certificates are up to date no need to renew' || {
        notify_nginx 'renewing_certs' \
        && certbot certonly --standalone --text  --agree-tos \
            --server https://acme-v02.api.letsencrypt.org/directory \
            --rsa-key-size 4096 --verbose --keep-until-expiring \
            --register-unsafely-without-email \
            --http-01-port 7000 \
            --preferred-challenges http \
            --config-dir $certs_dir/config \
            --work-dir $certs_dir/work \
            --logs-dir $certs_dir/logs \
            --test-cert \
            -d ${domain_name} \
        && notify_nginx "reload";
    }
}

setup_certbot && renew
