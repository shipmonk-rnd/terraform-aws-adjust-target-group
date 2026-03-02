variable "vpc_subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for Lambda to run within the VPC"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID for Lambda security group"
}

variable "name" {
  type        = string
  description = "Prefixing name for the Lambda function and associated resources"
}

variable "target_group_arn" {
  type        = string
  description = "ARN of the target group to update with Aurora endpoints IP addresses. Leave empty for discovery mode."
  default     = ""
}

variable "target_port" {
  type        = string
  description = "Port on which the target group is listening"
}

variable "type" {
  type        = string
  description = "Type of the target group, either 'reader' or 'writer'"
}

variable "identifier" {
  type        = string
  description = "ID of the Aurora cluster to fetch IP addresses from, or instance identifier for single RDS instance. Leave empty for discovery mode."
  default     = ""
}

variable "lambda_timeout" {
  type        = number
  description = "Timeout in seconds for the Lambda function. Discovery mode needs more time due to multiple API calls."
  default     = 60
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources created by this module"
  default     = {}
}
