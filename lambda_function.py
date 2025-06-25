import boto3
import os
import socket


def lambda_handler(event, context):
    db_identifier = os.environ['DB_IDENTIFIER']  # Can be cluster ID or instance ID
    target_group_arn = os.environ['TARGET_GROUP_ARN']
    target_port = int(os.environ.get('TARGET_PORT', 3306))
    target_type = os.environ.get('TYPE', 'reader').lower()  # 'reader', 'writer'

    rds = boto3.client('rds')
    elbv2 = boto3.client('elbv2')

    target_ips = []

    try:
        # Try to get it as a cluster first
        cluster_info = rds.describe_db_clusters(DBClusterIdentifier=db_identifier)['DBClusters'][0]
        print(f"Found Aurora cluster: {db_identifier}")
        target_ips = handle_aurora_cluster(rds, cluster_info, target_type)

    except rds.exceptions.DBClusterNotFoundFault:
        # Not a cluster, handle as single RDS instance
        print(f"Not a cluster, handling as single RDS instance: {db_identifier}")
        target_ips = handle_single_instance(rds, db_identifier, target_type)

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
        print(f"Deregistered IPs: {list(ips_to_remove)}")

    # Register any new targets
    ips_to_add = new_ips - current_ips
    if ips_to_add:
        elbv2.register_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': ip, 'Port': target_port} for ip in ips_to_add]
        )
        print(f"Registered IPs: {list(ips_to_add)}")

    return {
        'statusCode': 200,
        'body': f'Updated target group {target_group_arn} with {target_type} IPs: {list(new_ips)}'
    }


def handle_aurora_cluster(rds, cluster_info, target_type):
    """Handle Aurora cluster - original logic preserved"""
    cluster_identifier = cluster_info['DBClusterIdentifier']

    # First get cluster members and their roles
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
            reader_ip = socket.gethostbyname(reader_endpoint)
            target_ips.append(reader_ip)
    return target_ips


def handle_single_instance(rds, instance_identifier, target_type):
    """Handle single RDS instance"""
    instance_info = rds.describe_db_instances(DBInstanceIdentifier=instance_identifier)['DBInstances'][0]

    if instance_info['DBInstanceStatus'] != 'available':
        print(f"Instance {instance_identifier} is not available (status: {instance_info['DBInstanceStatus']})")
        return []

    endpoint = instance_info['Endpoint']['Address']
    ip_address = socket.gethostbyname(endpoint)

    if target_type == 'writer':
        # Include if it's not a read replica
        if not instance_info.get('ReadReplicaSourceDBInstanceIdentifier'):
            return [ip_address]
        else:
            print(f"Instance {instance_identifier} is a read replica, excluding from writer targets")
            return []
    elif target_type == 'reader':
        # Include if it's a read replica
        if instance_info.get('ReadReplicaSourceDBInstanceIdentifier'):
            return [ip_address]
        else:
            print(f"Instance {instance_identifier} is not a read replica, excluding from reader targets")
            return []

    return []
