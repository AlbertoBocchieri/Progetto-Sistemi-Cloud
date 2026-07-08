variable "aws_region" {
  type    = string
  default = "eu-south-1"
}

variable "project_name" {
  type    = string
  default = "parcheggia"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "enable_cloud_stack" {
  type        = bool
  default     = false
  description = "Set true only when you intentionally want paid AWS resources."
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "private_subnets" {
  type    = list(string)
  default = ["10.42.1.0/24", "10.42.2.0/24"]
}

variable "public_subnets" {
  type    = list(string)
  default = ["10.42.101.0/24", "10.42.102.0/24"]
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "mq_instance_type" {
  type    = string
  default = "mq.t3.micro"
}

variable "db_password" {
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
  description = "RDS password. Required only when enable_cloud_stack=true."

  validation {
    condition     = var.db_password == null || length(var.db_password) >= 16
    error_message = "db_password must be null or at least 16 characters."
  }
}

variable "mq_password" {
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
  description = "Amazon MQ RabbitMQ password. Required only when enable_cloud_stack=true."

  validation {
    condition     = var.mq_password == null || length(var.mq_password) >= 16
    error_message = "mq_password must be null or at least 16 characters."
  }
}
