#!/bin/bash

SCRIPTPATH="$( cd -P -- "$(dirname -- "$0")" && pwd -P )"
cd ${SCRIPTPATH}
if [[ -d ".venv" ]]; then
    source .venv/bin/activate && python -m healthcheck.healthcheckserverliveness
else
    python -m healthcheck.healthcheckserverliveness
fi
exit $?
