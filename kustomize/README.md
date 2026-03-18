# SSS Healthcheck Kubernetes Kustomize overlay configuration

Declarative management of SSS Healthcheck objects using Kustomize.

## How to use

Within an overlay directory, create a `.env` file to contain required secret
values in the format KEY=value (i.e. `overlays/uat/.env`).

Review the built resource output using `kustomize`:

```bash
kustomize build kustomize/overlays/uat/ | less
```

Run `kubectl` with the `-k` flag to generate resources for a given overlay:

```bash
kubectl apply -k kustomize/overlays/uat --namespace sss --dry-run=client
```

Required environment variables may include (some have defaults; check codebase):

    DEBUG
    HEALTHCHECKSERVER_HOST
    HEALTHCHECKSERVER_PORT
    AUTH2_USER
    AUTH2_PASSWORD

## References

- <https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/>
- <https://github.com/kubernetes-sigs/kustomize>
- <https://github.com/kubernetes-sigs/kustomize/tree/master/examples>
