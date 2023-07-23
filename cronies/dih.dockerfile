FROM debian:bullseye

RUN apt-get update && apt-get -y install apt-utils wget vim curl xz-utils cron procps 
RUN ln -sf /usr/share/zoneinfo/Africa/Nairobi /etc/localtime
RUN groupadd dih

WORKDIR /dih
ENV PATH="${PATH}:/dih/bin:/dih/lib/python/bin"
COPY --chown=root:dih  libs/python*.tar.xz lib/
COPY --chown=root:dih ./ cronies
COPY --chown=root:dih start.sh bin/start
COPY --chown=root:dih runuser.sh bin/runuser
WORKDIR /dih/cronies
RUN mkdir /dih/common \
    && chown :dih -R /dih \
    && chmod  770 -R /dih \
    && find /dih -type f -exec chmod  660 {} \; \
    && chmod +x /dih/bin/* 
ENTRYPOINT  /dih/bin/start
