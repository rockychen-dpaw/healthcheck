# SSS Healthcheck

Internal service endpoint health check for the Spatial Support System.

## Installation

Dependencies for this project are managed using [uv](https://docs.astral.sh/uv/).
With uv installed, change into the project directory and run:

    uv sync

Activate the virtualenv like so:

    source .venv/bin/activate

To run Python commands in the activated virtualenv, thereafter run them like so:

    ipython

Manage new or updated project dependencies with uv also, like so:

    uv add newpackage==1.0

## Environment variables

This project uses **python-dotenv** to set environment variables (in a `.env` file).
Most settings have default values; check `healthcheck/settings.py` for required variables.

The minimum required environment variables for the polling server are as follows:

    HEALTHCHECKSERVER_HOST
    HEALTHCHECKSERVER_PORT
    AUTH2_USER
    AUTH2_PASSWORD

## Running

Start the background headless polling server:

    python -m healthcheck.healthcheckserver

The polling server runs on port 9080 by default. Set `HEALTHCHECKSERVER_PORT` to change this.

Start the front-end application:

    hypercorn healthcheck.healthcheckapp:application --config hypercorn.toml

The front-end application runs on port 8080 by default. To change this, modify `hypercorn.toml`.

## Testing

Run unit tests using `pytest`:

    pytest -s --pdb

## Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/healthcheck .

To run a Docker container locally, publishing container port 8080 to a local port:

    docker container run --rm --publish 8080:8080 --env-file .env ghcr.io/dbca-wa/healthcheck

## Pre-commit hooks

This project includes the following pre-commit hooks:

- TruffleHog (credential scanning): <https://github.com/marketplace/actions/trufflehog-oss>

Pre-commit hooks may have additional system dependencies to run. Optionally
install pre-commit hooks locally like so:

    pre-commit install

Reference: <https://pre-commit.com/>
