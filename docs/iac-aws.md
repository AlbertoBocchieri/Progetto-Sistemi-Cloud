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
cd infrastructure/terraform/aws
cp terraform.tfvars.example terraform.tfvars
# modifica enable_cloud_stack = true solo quando vuoi creare risorse AWS
terraform init
terraform plan
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
