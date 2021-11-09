# Overview

The Healthcheck application serves an internal service endpoint health check for
the data services used by the Spatial Support System.

This repository contains resource definitions to deploy the application to a
Kubernetes cluster using Kustomize.

# Deployment

1. Create a `.env` file in this directory with required environmental variables
   in the format `KEY=value`.
2. Deploy using Kustomize, e.g. `kubectl apply -k .`
