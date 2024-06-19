#!/bin/bash

source common.sh

setup_tomcat() {

    [ -d /opt/tomcat ] && return

    apt-get install -y openjdk-11-jre-headless --fix-missing

    echo 'setting up tomcat'
    mkdir -p /opt/tomcat/ && cd /opt/tomcat
    url="https://archive.apache.org/dist/tomcat/tomcat-${tomcat_version:-9}"
    version=$(curl "$url/" -L 2>/dev/null | grep -Po '>v\K[^></]+' | sort | tail -1)
    wget -O apache-tomcat.tar.gz --progress=dot:giga "$url/v$version/bin/apache-tomcat-$version.tar.gz"
    tar xfz apache*.tar.gz && mv apache-tomcat*/* /opt/tomcat/.

    rm -rf apache* /opt/tomcat/webapps/*

    trim <<-EOF >>/opt/tomcat/bin/setenv.sh &&
        #!/bin/bash
        export JAVA_OPTS="$JAVA_OPTS -Xms1500m -Xmx2000m -Dfile.encoding=UTF8" #this is for a limited instance
        export DHIS2_HOME="/home/dhis/config"
EOF
        chmod +x /opt/tomcat/bin/setenv.sh
}

base='/dih'
setup_dhis2() {

    quiet id dhis && [ -f /home/dhis/config/dhis.conf ] && return

    echo 'setting up dhis2'
    useradd -d /home/dhis -m dhis -s /bin/false
    mkdir /home/dhis/config
    mv $base/conf/dhis.conf /home/dhis/config/dhis.conf
    chown -R dhis /home/dhis

    if [ -n $dhis_password ]; then
        sed -ri "s/connection.password.*/connection.password = $dhis_password/g" /home/dhis/config/dhis.conf
        unset dhis_password
    fi
    wget --progress=dot:giga -O ROOT.war ${dhis_war}
    mv ROOT.war /opt/tomcat/webapps/ROOT.war
}

fetch() {
    endpoint="$1" filter="$2"
    auth="admin:${3:-$dhis_admin_password}"
    url='http://localhost:8080/api'
    id=$(curl -s -u $auth "$url/$endpoint"?filter="$filter" | jq -r ".$endpoint[0].id")
    curl -s -u $auth "$url/$endpoint/$id"
}

put() {
    endpoint="$1"
    read -r data
    auth="admin:${2:-$dhis_admin_password}"
    id=$(echo $data | jq .id -r)
    url='http://localhost:8080/api'
    echo $data | curl -s -u $auth -X PUT -H "Content-type: application/json" $url/$endpoint/$id -d @- | {
        read results
        echo "$results" | grep -qP '\bOK\b' || (echo "$results" && return 1)
    }
}

change_admin_org() {
    org_id=$(fetch 'organisationUnits' 'level:eq:1' | jq -r .id)
    org_perms='{
        "organisationUnits": [{ "id": "'"$org_id"'" }],
        "dataViewOrganisationUnits": [{ "id": "'"$org_id"'" }],
        "teiSearchOrganisationUnits": [{ "id": "'"$org_id"'" }]
    }'
    echo $(fetch 'users' 'code:eq:admin' | jq ".+=$org_perms") | put "users"
    [ $? -eq 0 ] && echo 'successfully changed admin orgs' || echo ' could not change admin orgs'
}

change_admin_password() {
    #anchoring password field to same parent as previousPasswords field so since the path changes accroding to DHIS2 instance
    fetch users code:eq:admin "district" |
        sed -r 's/"previousPasswords"/"password":"'$(quote<<<"$dhis_admin_password")'","previousPasswords"/g'|
        put "users" "district"
    [ $? -eq 0 ] && echo 'successfully changed admin password' || echo ' could not change admin password'
}

ask_postgresql_to_change_admin_password() {
    echo change | nc -q 2 ${proj}-dhis_db 12345
}

import_metadata() {
    [ -f /data/.backup/metadata.json ] &&
        echo 'uploading metadata from metadata.json' &&
        curl -s -H 'Content-Type: application/json' \
            -u "admin:$dhis_admin_password" \
            -d @/data/.backup/metadata.json http://localhost:8080/api/metadata

    [ $? -eq 0 ] && [ -f /data/.backup/data_set.json ] &&
        echo 'uploading data_sets from data_set.json' &&
        curl -s -H 'Content-Type: application/json' \
            -u "admin:$dhis_admin_password" \
            -d @/data/.backup/data_set.json http://localhost:8080/api/metadata &&
        rm -rf /data.backup/metadata.json
}

on_war_deployed() {
    echo -e "\033[1;30m turning logs grayish till when war is released"
    while read -r line; do
        if echo "$line" | grep -qE 'Deployment of.*[/]ROOT.war.* has finished'; then
            echo "***** $line"
            change_admin_password &&
                import_metadata
            change_admin_org
            # && ask_postgresql_to_change_admin_password
            echo -e "\033[0m"
        else
            echo "$line"
        fi
    done < <(/opt/tomcat/bin/catalina.sh run 2>&1 &) && echo "War deployed"
}

wait_for_db_setup_first() {
    echo 'waiting for dhis2 database to be set'
    while read -r line && [[ $line != "dhis2_database_set" ]]; do echo "receive $line"; done < <(nc -l -p 12345)
}

wait_for_db_setup_first &&
    setup_tomcat &&
    setup_dhis2 &&
    on_war_deployed
