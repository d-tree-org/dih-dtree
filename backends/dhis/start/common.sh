#!/bin/bash

trim() { sed -r 's/^\s*//g;s/\s*$//g'; }
quiet() { "$@" &>/dev/null; }

setup_user() {
    [[ -z $dih_user ]] ||
        quiet id $dih_user ||
        [[ -f /home/$dih_user ]] && return 0

    useradd -m -g dih $dih_user
    chmod 770 -R /dih && chown -R :dih /dih
    chown -R $dih_user:dih /home/$dih_user

    for key in {proj,domain,domain_name,http_port,https_port}; do
        grep -rFl "\${$key}" /dih | xargs sed -ri "s/\\$\{$key\}/${!key}/g"
    done
}

setup_user
