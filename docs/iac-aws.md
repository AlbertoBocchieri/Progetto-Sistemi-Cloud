# IaC e AWS

## Ansible Locale

Check strumenti:

```bash
ansible-playbook -i infrastructure/ansible/inventory.ini infrastructure/ansible/playbooks/install-k8s-tools.yaml
```

Creazione VM Multipass:

```bash
ansible-playbook -i infrastructure/ansible/inventory.ini infrastructure/ansible/playbooks/setup-multipass.yaml
```

Bootstrap k3s:

```bash
ansible-playbook -i infrastructure/ansible/inventory.ini infrastructure/ansible/playbooks/bootstrap-cluster.yaml
```

Fallback leggero con k3d:

```bash
ansible-playbook -i infrastructure/ansible/inventory.ini infrastructure/ansible/playbooks/setup-k3d.yaml
scripts/k3d_prepare_local.sh
scripts/k8s_apply_local.sh
```

Runtime verificato su macOS Sequoia senza privilegi GUI Docker Desktop:

```bash
scripts/colima_start.sh
scripts/k3d_prepare_local.sh
scripts/k8s_apply_local.sh
```

## Terraform AWS

La configurazione e' in `infrastructure/terraform/aws`.

Di default `enable_cloud_stack = false`, quindi vengono preparati solo repository ECR. I servizi a costo continuo si abilitano esplicitamente:

```bash
cp infrastructure/terraform/aws/terraform.tfvars.example infrastructure/terraform/aws/terraform.tfvars
# modifica enable_cloud_stack = true solo quando vuoi creare risorse AWS
scripts/terraform_backend_bootstrap.sh
scripts/terraform_init.sh
terraform -chdir=infrastructure/terraform/aws plan
```

Password cloud:

```bash
export TF_VAR_db_password="..."
export TF_VAR_mq_password="..."
```

Risorse previste:

- ECR per immagini Docker;
- VPC;
- EKS;
- RDS PostgreSQL;
- ElastiCache Redis;
- Amazon MQ for RabbitMQ.

Prima di `terraform apply`, configurare le variabili sensitive e definire una strategia di destroy:

```bash
terraform destroy
```

Push immagini su ECR dopo `terraform apply` o dopo la creazione degli ECR:

```bash
scripts/aws_ecr_push.sh
```

## Cloud effimero sicuro

Per usare AWS solo il tempo di testare o fare demo:

```bash
export AWS_PROFILE=parcheggia-dev
export AWS_REGION=eu-south-1
scripts/cloud_plan.sh
CONFIRM_APPLY=apply-parcheggia-dev scripts/cloud_up.sh
scripts/cloud_status.sh
CONFIRM_DESTROY=destroy-parcheggia-dev scripts/cloud_down.sh
```

`cloud_up.sh` e `cloud_down.sh` richiedono conferme esplicite per evitare apply/destroy accidentali.
Con `enable_cloud_stack = false` restano solo ECR e lifecycle policy. Il destroy totale cancella anche i repository ECR e le immagini; per spegnere solo le risorse costose dopo una demo, rimetti `enable_cloud_stack = false`, esegui `scripts/cloud_plan.sh` e poi `CONFIRM_APPLY=apply-parcheggia-dev scripts/cloud_up.sh`.

## State Terraform remoto

Lo state Terraform usa un backend remoto:

- bucket S3 versionato `parcheggia-dev-terraform-state-<account-id>-<region>`;
- chiave `terraform/aws/terraform.tfstate`;
- cifratura S3 AES256;
- lock nativo S3 con `use_lockfile = true`.

Bootstrap o verifica del backend:

```bash
export AWS_PROFILE=parcheggia-dev
export AWS_REGION=eu-south-1
scripts/terraform_backend_bootstrap.sh
scripts/terraform_init.sh
```

Il backend non viene distrutto da `terraform destroy`, perche' contiene lo state necessario a sapere cosa esiste.
