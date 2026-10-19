# Security Hub CSPM (estándar AWS Foundational Security Best Practices) + GuardDuty (analiza VPC Flow Logs y DNS)
# + Amazon Inspector (CVEs de imágenes ECR / tareas). Hallazgos HIGH/CRITICAL -> SNS vía EventBridge.
resource "aws_securityhub_account" "main" {
  enable_default_standards = false
}

resource "aws_securityhub_standards_subscription" "fsbp" {
  standards_arn = "arn:aws:securityhub:${var.region}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

resource "aws_guardduty_detector" "main" {
  enable = true
}

resource "aws_inspector2_enabler" "main" {
  account_ids    = [data.aws_caller_identity.me.account_id]
  resource_types = ["ECR"]
}

resource "aws_cloudwatch_event_rule" "securityhub_high" {
  name = "securityhub-high-critical"
  event_pattern = jsonencode({
    source        = ["aws.securityhub"]
    "detail-type" = ["Security Hub Findings - Imported"]
    detail = { findings = {
      Severity = { Label = ["HIGH", "CRITICAL"] }
      Workflow = { Status = ["NEW"] }
    } }
  })
}

resource "aws_cloudwatch_event_target" "sns" {
  rule = aws_cloudwatch_event_rule.securityhub_high.name
  arn  = aws_sns_topic.alerts.arn
}

resource "aws_sns_topic_policy" "events" {
  arn = aws_sns_topic.alerts.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sns:Publish", Resource = aws_sns_topic.alerts.arn,
    Principal = { Service = ["events.amazonaws.com", "cloudwatch.amazonaws.com"] } }]
  })
}
