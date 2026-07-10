#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
CLUSTER_NAME="${CLUSTER_NAME:-parcheggia-dev}"
NAMESPACE="${NAMESPACE:-parcheggia}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
MANIFEST="${MANIFEST:-infrastructure/k8s/cloud-demo.yaml}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMPORT_OSM="${IMPORT_OSM:-true}"
AUTO_DOWN="${AUTO_DOWN:-true}"
AUTO_DOWN_AFTER_SECONDS="${AUTO_DOWN_AFTER_SECONDS:-14400}"
AUTO_DOWN_BACKEND="${AUTO_DOWN_BACKEND:-lambda}"

if [ "${CONFIRM_APPLY:-}" != "apply-parcheggia-dev" ]; then
  echo "Bloccato: usa CONFIRM_APPLY=apply-parcheggia-dev per accendere risorse AWS." >&2
  exit 2
fi

export AWS_PROFILE AWS_REGION CONFIRM_APPLY TF_DIR NAMESPACE

command -v aws >/dev/null 2>&1 || { echo "aws CLI is required." >&2; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "terraform is required." >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

scripts/cloud_up.sh

aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME" >/dev/null
scripts/k8s_cloud_config_from_aws.sh

kubectl -n "$NAMESPACE" create configmap zone-migrations \
  --from-file=001_create_zones.sql=services/zone-service/migrations/001_create_zones.sql \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NAMESPACE" delete job db-init --ignore-not-found
kubectl apply -f "$MANIFEST"

ecr_base="$(terraform -chdir="$TF_DIR" output -json ecr_repository_urls | python3 -c 'import json,sys; print(next(iter(json.load(sys.stdin).values())).rsplit("/", 1)[0])')"

for service in api-gateway frontend zone-service ingestion-service nemotron-service prediction-service location-service admin-service; do
  kubectl -n "$NAMESPACE" set image "deployment/${service}" "${service}=${ecr_base}/${service}:${IMAGE_TAG}"
done

kubectl -n "$NAMESPACE" wait --for=condition=complete job/db-init --timeout=300s

for deployment in zone-service ingestion-service nemotron-service prediction-service location-service admin-service api-gateway frontend; do
  kubectl -n "$NAMESPACE" rollout status "deployment/${deployment}" --timeout=300s
done

if [ "$IMPORT_OSM" = "true" ]; then
  scripts/k8s_import_osm_cloud.sh
fi

url=""
for _ in $(seq 1 60); do
  host="$(kubectl -n "$NAMESPACE" get service frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  if [ -n "$host" ]; then
    url="http://$host"
    break
  fi
  sleep 5
done

if [ -z "$url" ]; then
  echo "Deploy completato, ma il Load Balancer non ha ancora un hostname. Controlla con: kubectl -n $NAMESPACE get service frontend" >&2
  exit 3
fi

echo
echo "Load Balancer assegnato:"
echo "$url"

lb_name="${host%%-*}"
aws elb wait instance-in-service --load-balancer-name "$lb_name" >/dev/null 2>&1 || true

ready=false
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 "$url/" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 5
done

if [ "$ready" != "true" ] && command -v dig >/dev/null 2>&1; then
  ip="$(dig +short @1.1.1.1 "${url#http://}" | head -1)"
  if [ -n "$ip" ] && curl --resolve "${url#http://}:80:$ip" -fsS --max-time 5 "$url/" >/dev/null 2>&1; then
    echo "Nota: l'app risponde, ma il DNS locale potrebbe dover aggiornare la cache per qualche minuto."
    ready=true
  fi
fi

if [ "$ready" != "true" ]; then
  echo "Nota: URL assegnato, ma il controllo HTTP non e' ancora riuscito. Riprova fra 1-2 minuti." >&2
else
  echo
  echo "ParcheggIA cloud pronta:"
  echo "$url"
fi

echo
echo "Quando hai finito:"
echo "CONFIRM_DESTROY=destroy-parcheggia-dev scripts/cloud_down.sh"

if [ "$AUTO_DOWN" = "true" ]; then
  if [ "$AUTO_DOWN_BACKEND" = "lambda" ] && AUTO_DOWN_AFTER_SECONDS="$AUTO_DOWN_AFTER_SECONDS" scripts/cloud_schedule_auto_down.sh schedule; then
    :
  else
    echo "Fallback: uso auto-spegnimento locale." >&2
    AUTO_DOWN_AFTER_SECONDS="$AUTO_DOWN_AFTER_SECONDS" scripts/cloud_auto_down.sh schedule
  fi
fi
