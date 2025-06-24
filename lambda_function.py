import boto3
import os
import socket


def lambda_handler(event, context):
    cluster_identifier = os.environ['AURORA_CLUSTER_ID']
    target_group_arn = os.environ['TARGET_GROUP_ARN']
    target_port = int(os.environ.get('TARGET_PORT', 3306))
    target_type = os.environ.get('TYPE', 'reader').lower()  # 'reader' or 'writer'

    rds = boto3.client('rds')
    elbv2 = boto3.client('elbv2')

    # First get cluster members and their roles
    cluster_info = rds.describe_db_clusters(DBClusterIdentifier=cluster_identifier)['DBClusters'][0]
    cluster_members = {member['DBInstanceIdentifier']: 'writer' if member['IsClusterWriter'] else 'reader'
                       for member in cluster_info['DBClusterMembers']}

    instances = rds.describe_db_instances()['DBInstances']
    target_ips = []

    for instance in instances:
        if cluster_identifier != instance.get('DBClusterIdentifier', ''):
            continue

        instance_id = instance['DBInstanceIdentifier']
        instance_arn = instance['DBInstanceArn']

        # Check for autoscaled instance by presence of 'application-autoscaling:resourceId' tag
        tags_response = rds.list_tags_for_resource(ResourceName=instance_arn)
        tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagList', [])}

        if 'application-autoscaling:resourceId' in tags:
            continue

        instance_role = cluster_members.get(instance_id, 'unknown')
        endpoint = instance['Endpoint']
        ip_address = socket.gethostbyname(endpoint['Address'])

        if target_type == 'reader' and instance_role != 'reader':
            continue
        if target_type == 'writer' and instance_role != 'writer':
            continue

        target_ips.append(ip_address)

    # Fallback: no reader instance but request is for reader
    if target_type == 'reader' and not target_ips:
        reader_endpoint = cluster_info.get('ReaderEndpoint')
        if reader_endpoint:
            try:
                reader_ip = socket.gethostbyname(reader_endpoint)
                target_ips.append(reader_ip)
            except socket.error as e:
                print(f"Failed to resolve reader endpoint: {e}")

    # Retrieve current targets in the target group
    current_targets = elbv2.describe_target_health(TargetGroupArn=target_group_arn)
    current_ips = {target['Target']['Id'] for target in current_targets['TargetHealthDescriptions']}

    new_ips = set(target_ips)

    # Deregister any old targets not in the new set
    ips_to_remove = current_ips - new_ips
    if ips_to_remove:
        elbv2.deregister_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': ip} for ip in ips_to_remove]
        )

    # Register any new targets
    ips_to_add = new_ips - current_ips
    if ips_to_add:
        elbv2.register_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': ip, 'Port': target_port} for ip in ips_to_add]
        )

    return {
        'statusCode': 200,
        'body': f'Updated target group {target_group_arn} with {target_type} IPs: {list(new_ips)}'
    }
