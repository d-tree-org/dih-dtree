#!/bin/bash

source common.sh
function setup_tomcat(){

    [ -d /opt/tomcat ] && return;

    apt-get install -y openjdk-11-jre-headless netcat --fix-missing;

    echo 'setting up tomcat'
    mkdir -p /opt/tomcat/ && cd /opt/tomcat
    wget -O apache-tomcat.tar.gz --progress=dot:giga ${tomcat_url}
    tar xvfz apache*.tar.gz && mv apache-tomcat*/* /opt/tomcat/.

    rm -rf apache* /opt/tomcat/webapps/* 

    cat<<EOF | trim >>/opt/tomcat/bin/setenv.sh \
    && chmod +x /opt/tomcat/bin/setenv.sh
        #!/bin/bash
        export JAVA_OPTS="$JAVA_OPTS -Xms1500m -Xmx2000m -Dfile.encoding=UTF8" #this is for a limited instance
        export DHIS2_HOME="/home/dhis/config"
EOF
}

base='/dih'
function setup_dhis2(){

    quiet id dhis && [ -f /home/dhis/config/dhis.conf] && return; 

    echo 'setting up dhis2'
    useradd -d /home/dhis -m dhis -s /bin/false
    mkdir /home/dhis/config
    mv $base/conf/dhis.conf /home/dhis/config/dhis.conf
    chown -R dhis /home/dhis

    if [ -n $dhis_password ];
        then sed -ri "s/connection.password.*/connection.password = $dhis_password/g" /home/dhis/config/dhis.conf;
        unset dhis_password;
    fi
    wget --progress=dot:giga -O ROOT.war ${dhis_war} 
    mv ROOT.war /opt/tomcat/webapps/ROOT.war
}

admin_pass=$dhis_admin_password;
function set_admin_password(){

    [ -z $dhis_admin_password ] && return;

    echo "attempt to change the dhis admin password away from the default one"; 
    auth="admin:district"
    url='http://localhost:8080/api/users'
    user_id=$(curl -s -u $auth $url?filter=code:eq:admin | grep -Po 'id\W+\K\w+')

    [ -n $admin_pass ] && \
    curl -s -u $auth $url/$user_id |
        sed -r "s/\"previousPasswords/\"password\":\"$dhis_admin_password\",\"previousPasswords/g" |
        curl -u $auth -sX PUT -H "Content-type: application/json" $url/$user_id  -d @- |
        grep -qP '\bOK\b' && echo "successfully changed admin password" || echo "could not change password reusing the default"
    unset dhis_admin_password
}


function ask_postgresql_to_change_admin_password(){
    echo change | nc -q 2 ${proj}-dhis_db 12345
}


function import_metadata(){
    [ ! -f /data/.backup/metadata.json ] && return;
        curl -H 'Content-Type: application/json' \
            -u "admin:$admin_pass" \
            -d @/data/.backup/metadata.json  http://localhost:8080/api/metadata  \
        && curl -H 'Content-Type: application/json' \
            -u "admin:$admin_pass" \
            -d @/data/.backup/data_set.json  http://localhost:8080/api/metadata  \
        && rm -rf /data.backup/metadata.json
}



function on_war_deployed(){
    echo -e "\033[1;30m turning logs grayish till when war is released" 
    while read -r line; do
        if echo "$line" | grep -q 'Deployment of.*[/]ROOT.war.* has finished' ; then
            echo "***** $line"
            set_admin_password \
            && import_metadata \
            # && ask_postgresql_to_change_admin_password 
            echo -e "\033[0m"
        else
            echo $line
        fi
    done < <(/opt/tomcat/bin/catalina.sh run 2>&1 &) && echo "War deployed"
}

function wait_for_db_setup_first(){
  echo 'waiting for dhis2 database to be set'
  while read -r line && [[ $line != "dhis2_database_set" ]]; 
  do echo "receive $line"; done < <(nc -l -p 12345)
}


wait_for_db_setup_first \
&& setup_tomcat \
&& setup_dhis2 \
&& on_war_deployed