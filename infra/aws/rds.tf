# Amazon RDS for PostgreSQL 16 (base "inventory" de data-service) con Performance Insights y logs
resource "aws_db_subnet_group" "rds" {
  name       = "rds-lab"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_parameter_group" "pg16" {
  name   = "lab-pg16"
  family = "postgres16"
  parameter {
    name  = "log_min_duration_statement"
    value = "250"
  }
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }
}

resource "aws_iam_role" "rds_monitoring" {
  name = "lab-rds-enhanced-monitoring"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "monitoring.rds.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_instance" "inventory" {
  identifier                      = "rds-inventory"
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = "db.t4g.micro"
  allocated_storage               = 20
  db_name                         = "inventory"
  username                        = "app"
  password                        = var.db_password
  db_subnet_group_name            = aws_db_subnet_group.rds.name
  vpc_security_group_ids          = [aws_security_group.rds.id]
  parameter_group_name            = aws_db_parameter_group.pg16.name
  performance_insights_enabled    = true
  monitoring_interval             = 15
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports = ["postgresql"]
  skip_final_snapshot             = true
  storage_encrypted               = true
}
