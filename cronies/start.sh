#!/bin/bash
source /dih/cronies/functions.sh

function launch() {
    cron_log="/dih/cronies/logs/cron.log";
    setup_user &&
        create_run_command &&
        install_apt_dependencies &&
        quiet cron &&
        runuser -u $dih_user -- bash <<-CODE
        source /dih/cronies/functions.sh;
        should_initialize &&
            setup_python &&
            install_pip_dependencies &&
            install_cron
            echo "configuration log file is $cron_log"
            tail -f $cron_log || tail -f /dev/null
CODE
}

function add_cron() {
    setup_user &&
    install_apt_dependencies &&
        runuser -u $dih_user -- bash <<-CODE
        source /dih/cronies/functions.sh;
            install_pip_dependencies &&
            install_cron
CODE
}

case $1 in
    launch) launch ;;
    add_cron) add_cron ;;
esac
