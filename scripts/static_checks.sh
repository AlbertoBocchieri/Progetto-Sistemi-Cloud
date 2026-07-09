#!/usr/bin/env sh
set -eu

python3 -m py_compile services/zone-service/app/*.py services/ingestion-service/app/*.py services/nemotron-service/app/*.py services/prediction-service/app/*.py services/location-service/app/*.py services/admin-service/app/*.py scripts/check_*.py
python3 scripts/check_scoring.py
python3 scripts/check_tomtom.py
python3 scripts/audit_requirements.py
python3 scripts/check_scenarios.py
python3 scripts/check_contracts.py
python3 scripts/check_frontend.py
python3 scripts/check_osm_import.py
python3 scripts/check_parking_overrides.py
python3 scripts/check_road_backed_segments.py

find scripts -name "*.sh" -exec sh -n {} +

if command -v kubeconform >/dev/null 2>&1; then
  kubeconform -strict -summary infrastructure/k8s/local-demo.yaml
fi

if command -v docker >/dev/null 2>&1; then
  docker compose config >/dev/null
fi

if command -v terraform >/dev/null 2>&1 && [ -d infrastructure/terraform/aws/.terraform ]; then
  terraform -chdir=infrastructure/terraform/aws validate
fi

if command -v ansible-playbook >/dev/null 2>&1; then
  for playbook in infrastructure/ansible/playbooks/*.yaml; do
    ansible-playbook --syntax-check -i infrastructure/ansible/inventory.ini "$playbook" >/dev/null
  done
fi

if command -v ruby >/dev/null 2>&1; then
  ruby -e 'require "yaml"; Dir[".github/workflows/*.{yml,yaml}", "infrastructure/ansible/playbooks/*.{yml,yaml}"].each { |f| YAML.load_file(f) }'
fi

echo "Static checks OK"
