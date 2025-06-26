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
  description = "ARN of the target group to update with Aurora endpoints IP addresses"
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
  description = "ID of the Aurora cluster to fetch IP addresses from, or instance identifier for IDS instance"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources created by this module"
  default     = {}
}
