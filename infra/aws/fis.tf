# Módulo D — E1: inyección de 200 ms de latencia en service-b (Fargate) con AWS FIS.
# Guardrail: el experimento se detiene si la alarma de SLO de latencia permanece en ALARM (stop condition).
resource "aws_iam_role" "fis" {
  name = "lab-fis-experiments"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "fis.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "fis" {
  role = aws_iam_role.fis.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Resource = "*", Action = [
      "ecs:DescribeTasks", "ecs:ListTasks", "ssm:SendCommand", "ssm:ListCommands", "ssm:CancelCommand"
    ] }]
  })
}

resource "aws_fis_experiment_template" "e1_latency_service_b" {
  description = "E1 - latencia 200 ms en service-b (sandbox)"
  role_arn    = aws_iam_role.fis.arn

  stop_condition {
    source = "aws:cloudwatch:alarm"
    value  = aws_cloudwatch_metric_alarm.guardrail_availability.arn
  }

  target {
    name           = "service-b-tasks"
    resource_type  = "aws:ecs:task"
    selection_mode = "ALL"
    parameters = {
      cluster = aws_ecs_cluster.main.name
      service = aws_ecs_service.service_b.name
    }
  }

  action {
    name      = "latency-200ms"
    action_id = "aws:ecs:task-network-latency"
    target {
      key   = "Tasks"
      value = "service-b-tasks"
    }
    parameter {
      key   = "duration"
      value = "PT5M"
    }
    parameter {
      key   = "delayMilliseconds"
      value = "200"
    }
    parameter {
      key   = "useEcsFaultInjectionEndpoints"
      value = "true"
    }
  }

  tags = { Name = "E1-latency-service-b" }
}

# Guardrail de abortado: disponibilidad < 95 % durante 2 min
resource "aws_cloudwatch_metric_alarm" "guardrail_availability" {
  alarm_name          = "guardrail-service-b-availability"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 5
  metric_query {
    id          = "err"
    expression  = "100 * e5xx / MAX([req, 1])"
    return_data = true
  }
  metric_query {
    id = "e5xx"
    metric {
      namespace   = "AWS/ECS"
      metric_name = "HTTPCode_Target_5XX_Count"
      period      = 60
      stat        = "Sum"
      dimensions  = local.sc_dims
    }
  }
  metric_query {
    id = "req"
    metric {
      namespace   = "AWS/ECS"
      metric_name = "RequestCount"
      period      = 60
      stat        = "Sum"
      dimensions  = local.sc_dims
    }
  }
}
