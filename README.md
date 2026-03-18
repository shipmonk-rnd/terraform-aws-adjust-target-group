# Adjust target group based on the RDS Aurora Endpoints

This Lambda function automatically maintains ALB/NLB target group registrations for Aurora cluster or standalone RDS instance IP addresses based on their role (reader/writer).

### Functionality
- Dynamically updates target groups with RDS instance IP addresses
- Supports separate reader and writer endpoint management
- Supports Aurora clusters and standalone RDS instances
- Excludes auto-scaled instances from target registration
- Handles target group registration/deregistration automatically

### Operating Modes

#### Direct mode (default)

Provide `identifier` and `target_group_arn` to manage a specific RDS instance or Aurora cluster.

#### Discovery mode

Leave `identifier` and `target_group_arn` empty. The Lambda will scan all RDS clusters and standalone instances for a tag named `place_into_target_group` whose value is the target group ARN. All matching resources are synced automatically.

Tag your RDS resources like this:

```
place_into_target_group = "arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/my-tg/abc123"
```

Multiple RDS resources can point to the same or different target groups.

### Environment variables used in the Lambda function
- `DB_IDENTIFIER`: RDS instance or Aurora cluster identifier (empty for discovery mode)
- `TARGET_GROUP_ARN`: Target group ARN to manage (empty for discovery mode)
- `TARGET_PORT`: Database port (default: 3306)
- `TYPE`: Target type - 'reader' or 'writer' (default: 'reader')

### Use Case

Good for NLB used for AWS VPC Endpoints.

## Before you do anything in this module

Install pre-commit hooks by running following commands:

```shell script
brew install pre-commit terraform-docs
pre-commit install
```

<!-- BEGIN_TF_DOCS -->
## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_archive"></a> [archive](#provider\_archive) | n/a |
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_cloudwatch_event_rule.every_minute](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_target.lambda_target](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target) | resource |
| [aws_iam_role.lambda_execution_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.lambda_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_lambda_function.aurora_nlb](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_permission.allow_cloudwatch_to_call_lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_security_group.lambda_sg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [archive_file.lambda_zip](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/file) | data source |
| [aws_iam_policy_document.lambda_assume_role_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_identifier"></a> [identifier](#input\_identifier) | ID of the Aurora cluster to fetch IP addresses from, or instance identifier for single RDS instance. Leave empty for discovery mode. | `string` | `""` | no |
| <a name="input_lambda_timeout"></a> [lambda\_timeout](#input\_lambda\_timeout) | Timeout in seconds for the Lambda function. Discovery mode needs more time due to multiple API calls. | `number` | `60` | no |
| <a name="input_name"></a> [name](#input\_name) | Prefixing name for the Lambda function and associated resources | `string` | n/a | yes |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags to apply to all resources created by this module | `map(string)` | `{}` | no |
| <a name="input_target_group_arn"></a> [target\_group\_arn](#input\_target\_group\_arn) | ARN of the target group to update with Aurora endpoints IP addresses. Leave empty for discovery mode. | `string` | `""` | no |
| <a name="input_target_port"></a> [target\_port](#input\_target\_port) | Port on which the target group is listening | `string` | n/a | yes |
| <a name="input_type"></a> [type](#input\_type) | Type of the target group, either 'reader' or 'writer' | `string` | n/a | yes |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | VPC ID for Lambda security group | `string` | n/a | yes |
| <a name="input_vpc_subnet_ids"></a> [vpc\_subnet\_ids](#input\_vpc\_subnet\_ids) | Subnet IDs for Lambda to run within the VPC | `list(string)` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_function_name"></a> [function\_name](#output\_function\_name) | n/a |
<!-- END_TF_DOCS -->
