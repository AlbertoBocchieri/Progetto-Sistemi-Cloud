# Kubernetes Locale

Prerequisiti:

- cluster Kubernetes locale, per esempio k3s su Multipass;
- `kubectl` puntato al cluster;
- immagini Docker disponibili nel cluster.

Preset VM demo per macchine con 8 GB RAM:

```text
2 CPU, 3 GB RAM, 20 GB disco
```

Su macOS Sequoia, Docker Desktop aggiornato puo' richiedere una conferma amministratore GUI per configurare port mapping e socket. In una shell non interattiva il runtime verificato e' Colima:

```bash
brew install colima k3d kubernetes-cli helm
scripts/colima_start.sh
```

Fallback Kubernetes supportato:

```bash
scripts/k3d_prepare_local.sh
scripts/k8s_apply_local.sh
```

Build immagini:

```bash
docker compose build
```

Deploy:

```bash
scripts/k8s_apply_local.sh
```

Port-forward demo:

```bash
kubectl -n parcheggia port-forward svc/frontend 8080:80
kubectl -n parcheggia port-forward svc/api-gateway 8000:80
kubectl -n parcheggia port-forward svc/zone-service 8001:8000
kubectl -n parcheggia port-forward svc/ingestion-service 8002:8000
kubectl -n parcheggia port-forward svc/nemotron-service 8003:8000
kubectl -n parcheggia port-forward svc/prediction-service 8004:8000
kubectl -n parcheggia port-forward svc/location-service 8005:8000
kubectl -n parcheggia port-forward svc/admin-service 8006:8000
kubectl -n parcheggia port-forward svc/rabbitmq 15672:15672
```

Ingress demo, se il controller e' disponibile:

```text
http://parcheggia.local
```

Smoke test:

```bash
scripts/k8s_smoke_test.sh
```

Gate verificato il 2026-07-07 su macOS Sequoia:

```text
k3d cluster create -> OK
scripts/k8s_apply_local.sh -> OK
smoke/E2E/load via port-forward -> OK
```

Spegnimento dopo la demo:

```bash
k3d cluster delete parcheggia
colima stop
```
