resource "aws_elasticache_subnet_group" "main" {
  name       = local.cluster_full
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name        = "${local.cluster_full}-redis"
  description = "Allow Redis from EKS nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = local.cluster_full
  description          = "Redis for LangGraph agent checkpoints"

  node_type            = var.redis_node_type
  num_cache_clusters   = var.environment == "prod" ? 2 : 1
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = false   # set true with auth token in prod

  automatic_failover_enabled = var.environment == "prod"

  engine_version = "7.1"

  snapshot_retention_limit = var.environment == "prod" ? 1 : 0
}
