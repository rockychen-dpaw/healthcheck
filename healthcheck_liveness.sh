#!/bin/bash

if [[ "${start_healthcheckserver}" == "true" ]]; then
    if [[ -f "/tmp/healthcheckserver_started" ]]; then
        url="http://127.0.0.1:8080/healthcheck/ping"
    else
        if [[ ! -f "/tmp/healthcheckserver_starting" ]]; then
            SCRIPTPATH="$( cd -P -- "$(dirname -- "$0")" && pwd -P )"
            cd ${SCRIPTPATH}
            now=$(date +'%Y%m%dT%H%M%S')
            if [[ -d ".venv" ]]; then
                source .venv/bin/activate && nohup python -m healthcheck.healthcheckserver  > /tmp/healthcheckserver_${now}.log 2>&1  &
            else
                nohup python -m healthcheck.healthcheckserver  > /tmp/healthcheckserver_${now}.log 2>&1 &
            fi
            echo $(date +"%s") > /tmp/healthcheckserver_starting
            url="http://127.0.0.1:8080/livez"
        else
            starttime=$(cat /tmp/healthcheckserver_starting)
            now=$(date +'%s')
            starttingtime=$((now - starttime))
            if [[ ${starttingtime} -gt 30 ]]; then
                echo ${now} > /tmp/healthcheckserver_started
                url="http://127.0.0.1:8080/healthcheck/ping"
            else
                url="http://127.0.0.1:8080/livez"
            fi
        fi
    fi
else
    url="http://127.0.0.1:8080/livez"
fi
wget --timeout=0.5 ${url} -o /dev/null -O /dev/null
exit $?
