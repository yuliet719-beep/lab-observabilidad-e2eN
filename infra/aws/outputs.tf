output "ecs_cluster" { value = aws_ecs_cluster.main.name }
output "rds_endpoint" { value = aws_db_instance.inventory.address }
output "flow_log_group" { value = aws_cloudwatch_log_group.flow.name }
output "fis_e1_template" { value = aws_fis_experiment_template.e1_latency_service_b.id }
