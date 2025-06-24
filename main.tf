locals {
  common_tags = {
    owner      = "pd-dataengineering@shipmonk.com"
    app        = "data-platform"
    env        = "prod"
    permanency = "fixed"
    role       = "db"
    team       = "data-platform"
  }
}

resource "aws_security_group" "lambda_sg" {
  name        = "${var.name}-sg"
  description = "Security group for Lambda to access Aurora RDS"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.name}-role"

  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json

  tags = local.common_tags
}

data "aws_iam_policy_document" "lambda_assume_role_policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:RegisterTargets",
      "elasticloadbalancing:DeregisterTargets",
      "elasticloadbalancing:DescribeTargetHealth",
      "rds:ListTagsForResource",
      "rds:DescribeDBInstances",
      "rds:DescribeDBClusters",
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface"
    ]

    resources = ["*"]
  }
}
resource "aws_iam_role_policy" "lambda_policy" {
  name   = "${var.name}-policy"
  role   = aws_iam_role.lambda_execution_role.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "aurora_nlb" {
  function_name = "${var.name}-updater"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  role     = aws_iam_role.lambda_execution_role.arn
  filename = data.archive_file.lambda_zip.output_path

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  vpc_config {
    subnet_ids         = var.vpc_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      AURORA_CLUSTER_ID = var.aurora_cluster_id
      TARGET_GROUP_ARN  = var.target_group_arn
      TARGET_PORT       = var.target_port
      TYPE              = var.type
    }
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_event_rule" "every_minute" {
  name                = "${var.name}-minute"
  schedule_expression = "rate(1 minute)"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.every_minute.name
  target_id = "${var.name}-lambda"
  arn       = aws_lambda_function.aurora_nlb.arn
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_lambda" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.aurora_nlb.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_minute.arn
}
