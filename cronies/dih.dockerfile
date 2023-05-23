FROM debian

RUN apt-get update && apt-get -y install apt-utils wget vim curl xz-utils cron procps 
RUN groupadd dih

WORKDIR /dih
ENV PATH="${PATH}:/dih/bin:/dih/lib/python/bin"
COPY --chown=root:dih  libs/python*.tar.xz lib/
COPY --chown=root:dih ./ cronies
COPY --chown=root:dih start.sh bin/start
RUN chmod u+x bin/start \
    && mkdir /dih/common \
    && touch /dih/common/report_setup_done.log \
    && chown :dih -R /dih \
    && chmod  770 -R /dih 

ENTRYPOINT  /dih/bin/start