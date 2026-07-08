#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "README.md",
    "docker-compose.yml",
    ".env.example",
    ".nvmrc",
    "docs/architecture.md",
    "docs/api-spec.md",
    "docs/data-model.md",
    "docs/cloud-deployment.md",
    "docs/demo-script.md",
    "docs/test-plan.md",
    "docs/privacy.md",
    "docs/product-requirements.md",
    "docs/user-stories.md",
    "docs/event-flow.md",
    "docs/deployment-view.md",
    "docs/kubernetes-local.md",
    "docs/iac-aws.md",
    "docs/professor-presentation-outline.md",
    "docs/verification-matrix.md",
    "frontend/index.html",
    "frontend/app.js",
    "frontend/styles.css",
    "frontend/Dockerfile",
    "shared/openapi/parcheggia-api.yaml",
    "shared/schemas/events/parcheggia-event.schema.json",
    "shared/schemas/api/prediction.schema.json",
    "data/synthetic/demo_scenarios.json",
    "infrastructure/k8s/local-demo.yaml",
    "infrastructure/ansible/inventory.ini",
    "infrastructure/terraform/aws/main.tf",
    "infrastructure/terraform/aws/variables.tf",
    "infrastructure/terraform/aws/outputs.tf",
    "infrastructure/terraform/aws/terraform.tfvars.example",
    ".github/workflows/ci.yml",
    ".github/workflows/docker-build.yml",
    ".github/workflows/deploy-local.yml",
    ".github/workflows/deploy-eks.yml",
    ".github/workflows/terraform-plan.yml",
    ".github/workflows/terraform-apply.yml",
    "scripts/static_checks.sh",
    "scripts/run_checks.sh",
    "scripts/smoke_test.sh",
    "scripts/e2e_demo_test.sh",
    "scripts/load_test.sh",
    "scripts/k3d_prepare_local.sh",
    "scripts/k8s_apply_local.sh",
    "scripts/k8s_smoke_test.sh",
    "scripts/aws_ecr_push.sh",
    "scripts/colima_start.sh",
]

REQUIRED_SERVICES = [
    "zone-service",
    "location-service",
    "prediction-service",
    "ingestion-service",
    "admin-service",
    "nemotron-service",
]

REQUIRED_SERVICE_FILES = [
    "Dockerfile",
    "requirements.txt",
    "app/main.py",
]

REQUIRED_GATEWAY_FILES = [
    "services/api-gateway/Dockerfile",
    "services/api-gateway/nginx.conf",
]

REQUIRED_ANSIBLE_PLAYBOOKS = [
    "bootstrap-cluster.yaml",
    "install-k8s-tools.yaml",
    "setup-k3d.yaml",
    "setup-multipass.yaml",
]


def require_file(path: str) -> None:
    if not (ROOT / path).is_file():
        raise AssertionError(f"Missing required file: {path}")


def require_text(path: str, snippets: list[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        raise AssertionError(f"{path} missing snippets: {', '.join(missing)}")


def main() -> None:
    for path in REQUIRED_FILES + REQUIRED_GATEWAY_FILES:
        require_file(path)

    for service in REQUIRED_SERVICES:
        for filename in REQUIRED_SERVICE_FILES:
            require_file(f"services/{service}/{filename}")

    for playbook in REQUIRED_ANSIBLE_PLAYBOOKS:
        require_file(f"infrastructure/ansible/playbooks/{playbook}")

    require_text(
        "docker-compose.yml",
        [
            "postgres:",
            "redis:",
            "rabbitmq:",
            "api-gateway:",
            "frontend:",
            "admin-service:",
            "condition: service_completed_successfully",
        ],
    )
    require_text(
        "infrastructure/k8s/local-demo.yaml",
        [
            "kind: HorizontalPodAutoscaler",
            "kind: Ingress",
            "kind: Job",
            "name: admin-service",
            "name: prediction-service",
        ],
    )
    require_text(
        "infrastructure/terraform/aws/main.tf",
        [
            "aws_ecr_repository",
            "module \"eks\"",
            "aws_db_instance",
            "aws_elasticache_cluster",
            "aws_mq_broker",
            "aws_cloudwatch_log_group",
        ],
    )
    require_text(
        "frontend/index.html",
        [
            "Dashboard admin",
            "Destinazione",
            "Scenari demo",
            "Ho trovato posto",
        ],
    )

    print("Requirement audit OK")


if __name__ == "__main__":
    main()
