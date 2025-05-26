# SSS Healthcheck

Internal service endpoint health check for the Spatial Support System.

## Installation

The recommended way to set up this project for development is using
[uv](https://docs.astral.sh/uv/)
to install and manage a Python virtual environment.
With uv installed, install the required Python version (see `pyproject.toml`). Example:

    uv python install 3.12

Change into the project directory and run:

    uv python pin 3.12
    uv sync

Activate the virtualenv like so:

    source .venv/bin/activate

To run Python commands in the activated virtualenv, thereafter run them like so:

    ipython

Manage new or updated project dependencies with uv also, like so:

    uv add newpackage==1.0

## Environment variables

This project uses **python-dotenv** to set environment variables (in a `.env` file).
Most settings have default values; check `status.py` for required variables.

## Running

To run a local copy of the application:

    python status.py
    # Serve via HyperCorn instead of Quart:
    hypercorn status:application --config hypercorn.toml --reload

The application runs on port 8080 by default. To change this, modify `hypercorn.toml`.

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
