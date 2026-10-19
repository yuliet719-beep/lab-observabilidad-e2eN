# ECS Fargate + ECS Service Connect para service-b.
# Nota: AWS App Mesh llegó a fin de soporte el 30-sep-2026; Service Connect (Envoy gestionado) es su reemplazo
# y publica métricas L7 (RequestCount, TargetResponseTime, HTTPCode_Target_5XX_Count) por servicio.
resource "aws_ecs_cluster" "main" {
  name = "ecs-lab-e2e"
  setting {
    name  = "containerInsights"
    value = "enhanced"
  }
}

resource "aws_service_discovery_http_namespace" "mesh" {
  name = "lab.mesh"
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/lab/ecs/service-b"
  retention_in_days = 14
}

resource "aws_iam_role" "task_exec" {
  name = "lab-ecs-task-exec"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "task_exec" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "lab-ecs-task"
  assume_role_policy = aws_iam_role.task_exec.assume_role_policy
}

# ADOT: exportar a X-Ray, CloudWatch (EMF) y AMP; SSM para acciones FIS en Fargate
resource "aws_iam_role_policy" "task" {
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Resource = "*", Action = [
        "xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets",
        "logs:PutLogEvents", "logs:CreateLogStream", "logs:CreateLogGroup", "logs:DescribeLogStreams",
        "cloudwatch:PutMetricData", "aps:RemoteWrite",
        "ssm:CreateActivation", "ssm:AddTagsToResource"
      ] },
      { Effect = "Allow", Action = "iam:PassRole", Resource = aws_iam_role.ssm_managed.arn }
    ]
  })
}

resource "aws_iam_role" "ssm_managed" {
  name = "lab-fis-ssm-managed-instance"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ssm.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm_managed.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_ecs_task_definition" "service_b" {
  family                   = "service-b"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn
  enable_fault_injection   = true # requerido por AWS FIS (aws:ecs:task-network-latency)
  pid_mode                 = "task"

  container_definitions = jsonencode([
    {
      name         = "service-b"
      image        = var.service_b_image
      essential    = true
      portMappings = [{ name = "http", containerPort = 8000, protocol = "tcp", appProtocol = "http" }]
      environment = [
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://localhost:4317" },
        { name = "OTEL_SEMCONV_STABILITY_OPT_IN", value = "http,database" },
        { name = "CLOUD_PROVIDER", value = "aws" },
        { name = "CLOUD_PLATFORM", value = "aws_ecs" },
        { name = "CLOUD_REGION", value = var.region },
        { name = "DATA_SERVICE_URL", value = "http://data-service.lab.internal:10000" }
      ]
      logConfiguration = { logDriver = "awslogs", options = {
        awslogs-group = aws_cloudwatch_log_group.ecs.name, awslogs-region = var.region, awslogs-stream-prefix = "app"
      } }
    },
    {
      name      = "adot-collector"
      image     = "public.ecr.aws/aws-observability/aws-otel-collector:latest"
      essential = true
      command   = ["--config=/etc/ecs/ecs-default-config.yaml"]
      logConfiguration = { logDriver = "awslogs", options = {
        awslogs-group = aws_cloudwatch_log_group.ecs.name, awslogs-region = var.region, awslogs-stream-prefix = "adot"
      } }
    },
    {
      name        = "amazon-ssm-agent"
      image       = "public.ecr.aws/amazon-ssm-agent/amazon-ssm-agent:latest"
      essential   = false
      environment = [{ name = "MANAGED_INSTANCE_ROLE_NAME", value = aws_iam_role.ssm_managed.name }]
    }
  ])
}

resource "aws_ecs_service" "service_b" {
  name            = "service-b"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.service_b.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.service_b.id]
  }

  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.mesh.arn
    service {
      port_name      = "http"
      discovery_name = "service-b"
      client_alias {
        port     = 10000
        dns_name = "service-b"
      }
    }
    log_configuration {
      log_driver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "service-connect"
      }
    }
  }
}
