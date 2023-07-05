#!/bin/bash

#  usr=$1
#  version=$2
 source <( printenv )
 useradd -m $usr -g dih -s /bin/bash -d /home/$usr
 cd /home/$usr

function build_python(){
    apt-get update && apt-get -y install apt-utils wget vim curl git xz-utils cron procps\
    libffi-dev libgdbm-dev libsqlite3-dev libssl-dev zlib1g-dev build-essential\
    libncurses5-dev libbz2-dev libreadline-dev

    tar=Python-${version}.tar.xz
    runuser -u $usr -- bash <<-CMD
        mkdir -p /home/${usr}/Downloads
        mkdir -p /home/${usr}/.bin
        cd /home/${usr}/Downloads 
        wget -O $tar --progress=dot:giga  https://www.python.org/ftp/python/${version}/${tar}
        tar -xvf $tar
        cd /home/${usr}/Downloads/Python-${version}
        ./configure \
                --enable-optimizations \
                --prefix=/dih/lib/python \
                --with-ensurepip=install \
                --without-tests \
                --enable-ipv6 
                # LDFLAGS=-Wl,-rpath=/opt/python/{$version}/lib,--disable-new-dtags
        make clean
        make
        make install 
        cd /home/$usr/.bin/
        rm -f python pip
        ln -s /dih/lib/python/bin/python3 python
        ln -s /dih/lib/python/bin/pip3 pip
CMD
}


function remove_unused(){

    #clean what we no longer need
    apt remove -y --purge python libffi-dev libgdbm-dev libsqlite3-dev libssl-dev zlib1g-dev build-essential 
    apt -y autoremove
    cd  /home/${usr}/
    rm -rf  /var/lib/apt/lists/* Downloads Python-${version}

}


function check_if_installed_ok(){
   export PATH="$PATH:/home/$usr/.bin"
   runuser -u $usr -- python --version
   runuser -u $usr -- pip --version
}


function compress(){
    cd /dih/lib/
    tar -cJf /built/python-$version.tar.xz --preserve-permissions  python 
    # rm -r /home/$usr/.bin/python
}


build_python \
&& check_if_installed_ok \
&& compress
# && remove_unused \
