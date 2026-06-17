resource "aws_security_group" "msk" {
  name        = "${local.cluster_full}-msk"
  description = "Allow Kafka from EKS nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 9092
    to_port         = 9092
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_msk_cluster" "main" {
  cluster_name           = local.cluster_full
  kafka_version          = "3.6.0"
  number_of_broker_nodes = var.msk_broker_count

  broker_node_group_info {
    instance_type   = var.msk_broker_instance_type
    client_subnets  = slice(module.vpc.private_subnets, 0, var.msk_broker_count)
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = 100
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "PLAINTEXT"   # use TLS in prod
      in_cluster    = true
    }
  }

  # KRaft mode — no ZooKeeper
  broker_node_group_info {
    instance_type  = var.msk_broker_instance_type
    client_subnets = slice(module.vpc.private_subnets, 0, var.msk_broker_count)
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = 100
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  lifecycle {
    ignore_changes = [broker_node_group_info]
  }
}

resource "aws_msk_configuration" "main" {
  kafka_versions = ["3.6.0"]
  name           = local.cluster_full

  server_properties = <<-PROPS
    auto.create.topics.enable=true
    default.replication.factor=2
    min.insync.replicas=1
    num.partitions=3
    log.retention.hours=168
  PROPS
}
