locals {
  name                    = "${var.project_name}-${var.environment}"
  auto_down_schedule_name = "${local.name}-auto-down"
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

data "aws_caller_identity" "current" {}

data "archive_file" "auto_down_dispatcher" {
  type        = "zip"
  source_file = "${path.module}/lambda/auto_down_dispatcher.py"
  output_path = "${path.module}/.terraform/auto_down_dispatcher.zip"
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

resource "aws_cloudwatch_log_group" "auto_down_dispatcher" {
  name              = "/aws/lambda/${local.name}-auto-down-dispatcher"
  retention_in_days = 7

  tags = local.tags
}

resource "aws_iam_role" "auto_down_dispatcher" {
  name = "${local.name}-auto-down-dispatcher"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "auto_down_dispatcher" {
  name = "${local.name}-auto-down-dispatcher"
  role = aws_iam_role.auto_down_dispatcher.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.auto_down_dispatcher.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = "ssm:GetParameter"
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.github_actions_token_parameter}"
      },
      {
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_lambda_function" "auto_down_dispatcher" {
  function_name    = "${local.name}-auto-down-dispatcher"
  description      = "Dispatches the GitHub Actions cloud-down workflow for ParcheggIA demos."
  role             = aws_iam_role.auto_down_dispatcher.arn
  handler          = "auto_down_dispatcher.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.auto_down_dispatcher.output_path
  source_code_hash = data.archive_file.auto_down_dispatcher.output_base64sha256
  timeout          = 20
  memory_size      = 128
  architectures    = ["arm64"]

  environment {
    variables = {
      GITHUB_TOKEN_PARAMETER = var.github_actions_token_parameter
      GITHUB_OWNER           = var.github_owner
      GITHUB_REPO            = var.github_repo
      GITHUB_REF             = var.github_ref
      GITHUB_WORKFLOW        = var.github_down_workflow
    }
  }

  depends_on = [aws_cloudwatch_log_group.auto_down_dispatcher]

  tags = local.tags
}

resource "aws_iam_role" "auto_down_scheduler" {
  name = "${local.name}-auto-down-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "auto_down_scheduler" {
  name = "${local.name}-auto-down-scheduler"
  role = aws_iam_role.auto_down_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.auto_down_dispatcher.arn
      }
    ]
  })
}

resource "aws_lambda_permission" "auto_down_scheduler" {
  statement_id  = "AllowEventBridgeSchedulerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_down_dispatcher.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = "arn:aws:scheduler:${var.aws_region}:${data.aws_caller_identity.current.account_id}:schedule/default/${local.auto_down_schedule_name}"
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
  cluster_version = "1.35"

  cluster_endpoint_public_access           = true
  enable_cluster_creator_admin_permissions = true

  vpc_id     = module.vpc[0].vpc_id
  subnet_ids = module.vpc[0].private_subnets

  node_security_group_additional_rules = {
    ingress_self_http = {
      description = "Allow pod-to-pod HTTP traffic between EKS nodes"
      protocol    = "tcp"
      from_port   = 80
      to_port     = 80
      type        = "ingress"
      self        = true
    }
  }

  eks_managed_node_groups = {
    default = {
      instance_types = ["t4g.small"]
      ami_type       = "AL2023_ARM_64_STANDARD"
      min_size       = 1
      max_size       = 2
      desired_size   = 2
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

  broker_name                = "${local.name}-rabbitmq"
  engine_type                = "RabbitMQ"
  engine_version             = "3.13"
  host_instance_type         = var.mq_instance_type
  auto_minor_version_upgrade = true
  publicly_accessible        = false
  subnet_ids                 = [module.vpc[0].private_subnets[0]]
  security_groups            = [aws_security_group.managed_services[0].id]

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
