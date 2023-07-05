FROM debian:bullseye

RUN apt-get update && apt-get -y install apt-utils wget vim curl xz-utils cron procps libterm-readline-gnu-perl libbz2-dev ssh-client postgresql-client zip
RUN ln -sf /usr/share/zoneinfo/Africa/Nairobi /etc/localtime
RUN groupadd dih

WORKDIR /dih
ENV PATH="${PATH}:/dih/bin:/dih/lib/python/bin"
COPY --chown=root:dih bin/*.sh bin/
WORKDIR /dih/cronies
RUN mkdir -p /dih/common /dih/lib \
    && chown :dih -R /dih \
    && chmod  770 -R /dih \
    && mv  /dih/bin/start.sh /dih/bin/start \
    && mv  /dih/bin/run.sh /dih/bin/run \
    && find /dih -type f -exec chmod  660 {} \; \
    && chmod +x /dih/bin/* 
ENTRYPOINT  /dih/bin/start
