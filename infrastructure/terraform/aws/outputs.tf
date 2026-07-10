output "ecr_repository_urls" {
  value = {
    for name, repo in aws_ecr_repository.services : name => repo.repository_url
  }
}

output "eks_cluster_name" {
  value = var.enable_cloud_stack ? module.eks[0].cluster_name : null
}

output "cloudwatch_log_groups" {
  value = {
    for name, log_group in aws_cloudwatch_log_group.services : name => log_group.name
  }
}

output "rds_endpoint" {
  value = var.enable_cloud_stack ? aws_db_instance.postgres[0].address : null
}

output "redis_endpoint" {
  value = var.enable_cloud_stack ? aws_elasticache_cluster.redis[0].cache_nodes[0].address : null
}

output "rabbitmq_endpoint" {
  value = var.enable_cloud_stack ? aws_mq_broker.rabbitmq[0].instances[0].endpoints : null
}

output "auto_down_lambda_arn" {
  value = aws_lambda_function.auto_down_dispatcher.arn
}

output "auto_down_scheduler_role_arn" {
  value = aws_iam_role.auto_down_scheduler.arn
}

output "auto_down_schedule_name" {
  value = local.auto_down_schedule_name
}
