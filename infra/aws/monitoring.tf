# ---------- AIOps (Módulo B) ----------
# DevOps Guru deja de aceptar clientes nuevos el 29-oct-2026 (fin de soporte 30-sep-2027);
# AWS recomienda CloudWatch Anomaly Detection como reemplazo para detección de anomalías en métricas.
resource "aws_sns_topic" "alerts" { name = "lab-alerts" }

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  sc_dims = { ClusterName = aws_ecs_cluster.main.name, ServiceName = aws_ecs_service.service_b.name, DiscoveryName = "service-b" }
}

# (1) error_rate > banda de anomalía (≈ baseline + 2σ)
resource "aws_cloudwatch_metric_alarm" "error_rate_anomaly" {
  alarm_name          = "aiops-service-b-error-rate-anomaly"
  comparison_operator = "GreaterThanUpperThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold_metric_id = "band"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(err, 2)"
    label       = "banda ±2σ"
    return_data = true
  }
  metric_query {
    id          = "err"
    expression  = "100 * e5xx / MAX([req, 1])"
    label       = "error rate %"
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

# (2) latency p99 > SLO_threshold
resource "aws_cloudwatch_metric_alarm" "latency_p99_slo" {
  alarm_name          = "aiops-service-b-latency-p99-slo"
  namespace           = "AWS/ECS"
  metric_name         = "TargetResponseTime"
  extended_statistic  = "p99"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.slo_latency_threshold_ms
  dimensions          = local.sc_dims
  treat_missing_data  = "notBreaching"
}

# (3) Regla de correlación: (1) Y (2) -> una sola página
resource "aws_cloudwatch_composite_alarm" "correlated" {
  alarm_name        = "aiops-service-b-correlated-error-latency"
  alarm_rule        = "ALARM(${aws_cloudwatch_metric_alarm.error_rate_anomaly.alarm_name}) AND ALARM(${aws_cloudwatch_metric_alarm.latency_p99_slo.alarm_name})"
  alarm_actions     = [aws_sns_topic.alerts.arn]
  ok_actions        = [aws_sns_topic.alerts.arn]
  alarm_description = "error_rate > baseline+2σ Y p99 > SLO. El correlador consulta X-Ray (trace_id del request fallido)."
  actions_suppressor {
    alarm            = aws_cloudwatch_metric_alarm.fis_running.alarm_name
    extension_period = 0
    wait_period      = 0
  }
}

# Supresor: evita duplicar páginas mientras corre un experimento FIS conocido (se usa solo si se desea)
resource "aws_cloudwatch_metric_alarm" "fis_running" {
  alarm_name          = "fis-experiment-running"
  namespace           = "Lab/Chaos"
  metric_name         = "ExperimentActive"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
}

# Anomaly detection sobre latencia de lectura de RDS (dependencia de data-service)
resource "aws_cloudwatch_metric_alarm" "rds_latency_anomaly" {
  alarm_name          = "aiops-rds-read-latency-anomaly"
  comparison_operator = "GreaterThanUpperThreshold"
  evaluation_periods  = 3
  threshold_metric_id = "band"
  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(lat, 2)"
    return_data = true
  }
  metric_query {
    id          = "lat"
    return_data = true
    metric {
      namespace   = "AWS/RDS"
      metric_name = "ReadLatency"
      period      = 60
      stat        = "Average"
      dimensions  = { DBInstanceIdentifier = aws_db_instance.inventory.identifier }
    }
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ---------- Network & Security (Módulo C) ----------
resource "aws_cloudwatch_log_metric_filter" "rejects" {
  name           = "vpc-flow-rejects"
  log_group_name = aws_cloudwatch_log_group.flow.name
  pattern        = "[version, account, eni, srcaddr, dstaddr, srcport, dstport, protocol, packets, bytes, start, end, action=\"REJECT\", ...]"
  metric_transformation {
    name      = "RejectedFlows"
    namespace = "Lab/Network"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "unexpected_rds" {
  name           = "vpc-flow-unexpected-rds"
  log_group_name = aws_cloudwatch_log_group.flow.name
  pattern        = "[version, account, eni, srcaddr!=\"10.24.*\", dstaddr, srcport, dstport=5432, protocol, packets, bytes, start, end, action=\"ACCEPT\", ...]"
  metric_transformation {
    name      = "UnexpectedRdsFlows"
    namespace = "Lab/Network"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "auth_failures" {
  name           = "auth-failures"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  pattern        = "\"security.auth.failure\""
  metric_transformation {
    name      = "AuthFailures"
    namespace = "Lab/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "rejects_spike" {
  alarm_name          = "sec-vpc-rejected-flows-spike"
  comparison_operator = "GreaterThanUpperThreshold"
  evaluation_periods  = 2
  threshold_metric_id = "band"
  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(rej, 3)"
    return_data = true
  }
  metric_query {
    id          = "rej"
    return_data = true
    metric {
      namespace   = "Lab/Network"
      metric_name = "RejectedFlows"
      period      = 60
      stat        = "Sum"
    }
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "unexpected_rds" {
  alarm_name          = "sec-unexpected-east-west-to-rds"
  namespace           = "Lab/Network"
  metric_name         = "UnexpectedRdsFlows"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_dashboard" "security" {
  dashboard_name = "Golden-Signals-Seguridad"
  dashboard_body = jsonencode({
    widgets = [
      { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = {
        title = "Intentos de autenticación fallidos", region = var.region, stat = "Sum", period = 60,
      metrics = [["Lab/Security", "AuthFailures"]] } },
      { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = {
        title = "Flujos REJECT y flujos no permitidos a RDS", region = var.region, stat = "Sum", period = 60,
      metrics = [["Lab/Network", "RejectedFlows"], ["Lab/Network", "UnexpectedRdsFlows"]] } },
      { type = "log", x = 0, y = 6, width = 24, height = 6, properties = {
        title = "Tráfico N-S vs E-W (bytes por flow-direction)", region = var.region,
        query = "SOURCE '${aws_cloudwatch_log_group.flow.name}' | parse @message '* * * * * * * * * * * * * * * * *' as v, acc, eni, src, dst, sp, dp, proto, pk, by, st, en, act, ls, vpc, dir, path | stats sum(by) as bytes by dir, bin(1m)",
      view = "timeSeries" } },
      { type = "metric", x = 0, y = 12, width = 24, height = 6, properties = {
        title = "Hallazgos activos Security Hub / Inspector (CVEs)", region = var.region, stat = "Maximum", period = 300,
      metrics = [["Lab/Security", "ActiveFindings", "Severity", "CRITICAL"], ["Lab/Security", "ActiveFindings", "Severity", "HIGH"]] } }
    ]
  })
}
