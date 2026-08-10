# SecureDox Minikube

These manifests demonstrate local Kubernetes platform readiness:

- Deployments for API, worker, web, Postgres, and Redis.
- Services for internal routing.
- Nginx Ingress.
- ConfigMap and Secret example.
- Readiness and liveness probes.
- Rolling update strategies.
- HPA for API and worker.

## Local Deploy

```bash
minikube start
minikube addons enable ingress
eval $(minikube docker-env)
docker compose -f infra/docker/docker-compose.yml build api worker web
docker tag securedox/api:local docker.io/securedox/api:local
docker tag securedox/worker:local docker.io/securedox/worker:local
docker tag securedox/web:local docker.io/securedox/web:local
kubectl apply -k infra/k8s/minikube/base
kubectl -n securedox get pods
```

Add `$(minikube ip) securedox.local` to `/etc/hosts`, then open
`http://securedox.local`.

## Validate

```bash
kubectl apply -k infra/k8s/minikube/base --dry-run=client
trivy config infra/k8s
```
