FROM debian

 RUN apt-get update && apt-get -y install apt-utils wget vim curl git xz-utils cron procps\
    libffi-dev libgdbm-dev libsqlite3-dev libssl-dev zlib1g-dev build-essential\
    libncurses5-dev libbz2-dev libreadline-dev

COPY build_python.sh  /usr/bin/build_python
RUN  groupadd dih \
        && mkdir -p /dih \
        && chown :dih -R /dih \
        && chmod 770 /dih \
        && chmod +x /usr/bin/build_python

CMD tail -f /dev/null
