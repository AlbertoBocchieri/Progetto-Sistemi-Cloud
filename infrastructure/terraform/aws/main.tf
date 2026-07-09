locals {
  name = "${var.project_name}-${var.environment}"
  service_names = [
    "api-gateway",
    "frontend",
    "zone-service",
    "ingestion-service",
    "nemotron-service",
    "prediction-service",
    "location-service",
    "admin-service",
  ]
  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.service_names)

  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each = aws_ecr_repository.services

  repository = each.value.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 10
        description  = "Keep only the last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "services" {
  for_each = var.enable_cloud_stack ? toset(local.service_names) : toset([])

  name              = "/aws/parcheggia/${local.name}/${each.key}"
  retention_in_days = 7

  tags = local.tags
}

module "vpc" {
  count   = var.enable_cloud_stack ? 1 : 0
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = local.tags
}

module "eks" {
  count   = var.enable_cloud_stack ? 1 : 0
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.name
  cluster_version = "1.30"

  vpc_id     = module.vpc[0].vpc_id
  subnet_ids = module.vpc[0].private_subnets

  eks_managed_node_groups = {
    default = {
      instance_types = ["t3.small"]
      min_size       = 1
      max_size       = 2
      desired_size   = 1
    }
  }

  tags = local.tags
}

resource "aws_security_group" "managed_services" {
  count = var.enable_cloud_stack ? 1 : 0

  name        = "${local.name}-managed-services"
  description = "ParcheggIA managed service access from the VPC"
  vpc_id      = module.vpc[0].vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    from_port   = 5671
    to_port     = 5672
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_db_subnet_group" "postgres" {
  count = var.enable_cloud_stack ? 1 : 0

  name       = "${local.name}-postgres"
  subnet_ids = module.vpc[0].private_subnets

  tags = local.tags
}

resource "aws_db_instance" "postgres" {
  count = var.enable_cloud_stack ? 1 : 0

  identifier              = "${local.name}-postgres"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = var.rds_instance_class
  allocated_storage       = 20
  db_name                 = "parcheggia"
  username                = "parcheggia"
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.postgres[0].name
  vpc_security_group_ids  = [aws_security_group.managed_services[0].id]
  skip_final_snapshot     = true
  backup_retention_period = 1
  publicly_accessible     = false

  lifecycle {
    precondition {
      condition     = var.db_password != null && length(var.db_password) >= 16
      error_message = "db_password is required and must be at least 16 characters when enable_cloud_stack=true."
    }
  }

  tags = local.tags
}

resource "aws_elasticache_subnet_group" "redis" {
  count = var.enable_cloud_stack ? 1 : 0

  name       = "${local.name}-redis"
  subnet_ids = module.vpc[0].private_subnets

  tags = local.tags
}

resource "aws_elasticache_cluster" "redis" {
  count = var.enable_cloud_stack ? 1 : 0

  cluster_id           = "${local.name}-redis"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis[0].name
  security_group_ids   = [aws_security_group.managed_services[0].id]

  tags = local.tags
}

resource "aws_mq_broker" "rabbitmq" {
  count = var.enable_cloud_stack ? 1 : 0

  broker_name         = "${local.name}-rabbitmq"
  engine_type         = "RabbitMQ"
  engine_version      = "3.13"
  host_instance_type  = var.mq_instance_type
  publicly_accessible = false
  subnet_ids          = [module.vpc[0].private_subnets[0]]
  security_groups     = [aws_security_group.managed_services[0].id]

  user {
    username = "parcheggia"
    password = var.mq_password
  }

  lifecycle {
    precondition {
      condition     = var.mq_password != null && length(var.mq_password) >= 16
      error_message = "mq_password is required and must be at least 16 characters when enable_cloud_stack=true."
    }
  }

  tags = local.tags
}
