import boto3
import os
import socket
from collections import defaultdict

socket.setdefaulttimeout(5)


def lambda_handler(event, context):
    db_identifier = os.environ.get('DB_IDENTIFIER', '')
    target_group_arn = os.environ.get('TARGET_GROUP_ARN', '')
    target_port = int(os.environ.get('TARGET_PORT', 3306))
    target_type = os.environ.get('TYPE', 'reader').lower()  # 'reader', 'writer'

    rds = boto3.client('rds')
    elbv2 = boto3.client('elbv2')

    if not db_identifier:
        # Discovery mode: scan all RDS resources for place_into_target_group tag
        print("No DB_IDENTIFIER set, entering discovery mode")
        return discover_and_sync(rds, elbv2, target_type, target_port)

    # Direct mode: existing behavior
    target_ips = []

    try:
        cluster_info = rds.describe_db_clusters(DBClusterIdentifier=db_identifier)['DBClusters'][0]
        print(f"Found Aurora cluster: {db_identifier}")
        target_ips = handle_aurora_cluster(rds, cluster_info, target_type)

    except rds.exceptions.DBClusterNotFoundFault:
        print(f"Not a cluster, handling as single RDS instance: {db_identifier}")
        instance_info = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)['DBInstances'][0]
        target_ips = handle_single_instance(instance_info, target_type)

    sync_target_group(elbv2, target_group_arn, set(target_ips), target_port)

    return {
        'statusCode': 200,
        'body': f'Updated target group {target_group_arn} with {target_type} IPs: {list(target_ips)}'
    }


def sync_target_group(elbv2, target_group_arn, new_ips, target_port):
    """Deregister stale targets and register new ones for a target group."""
    current_targets = elbv2.describe_target_health(TargetGroupArn=target_group_arn)
    current_ips = {target['Target']['Id'] for target in current_targets['TargetHealthDescriptions']}

    ips_to_remove = current_ips - new_ips
    if ips_to_remove:
        elbv2.deregister_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': ip} for ip in ips_to_remove]
        )
        print(f"[{target_group_arn}] Deregistered IPs: {list(ips_to_remove)}")

    ips_to_add = new_ips - current_ips
    if ips_to_add:
        elbv2.register_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': ip, 'Port': target_port} for ip in ips_to_add]
        )
        print(f"[{target_group_arn}] Registered IPs: {list(ips_to_add)}")


def handle_aurora_cluster(rds, cluster_info, target_type, all_instances=None):
    """Handle Aurora cluster. If all_instances is provided, use it instead of calling describe_db_instances."""
    cluster_identifier = cluster_info['DBClusterIdentifier']

    cluster_members = {member['DBInstanceIdentifier']: 'writer' if member['IsClusterWriter'] else 'reader'
                       for member in cluster_info['DBClusterMembers']}

    if all_instances is None:
        instances = rds.describe_db_instances()['DBInstances']
    else:
        instances = all_instances

    target_ips = []

    for instance in instances:
        if cluster_identifier != instance.get('DBClusterIdentifier', ''):
            continue

        instance_id = instance['DBInstanceIdentifier']
        instance_arn = instance['DBInstanceArn']

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


def handle_single_instance(instance_info, target_type):
    """Handle single RDS instance. Accepts instance info dict directly."""
    instance_identifier = instance_info['DBInstanceIdentifier']

    if instance_info['DBInstanceStatus'] not in ['available', 'backing-up', 'modifying']:
        print(f"Instance {instance_identifier} is not available (status: {instance_info['DBInstanceStatus']})")
        return []

    endpoint = instance_info['Endpoint']['Address']
    ip_address = socket.gethostbyname(endpoint)

    if target_type == 'writer':
        if not instance_info.get('ReadReplicaSourceDBInstanceIdentifier'):
            return [ip_address]
        else:
            print(f"Instance {instance_identifier} is a read replica, excluding from writer targets")
            return []
    elif target_type == 'reader':
        if instance_info.get('ReadReplicaSourceDBInstanceIdentifier'):
            return [ip_address]
        else:
            print(f"Instance {instance_identifier} is not a read replica, excluding from reader targets")
            return []

    return []


def get_all_db_instances(rds):
    """Fetch all DB instances using pagination."""
    instances = []
    paginator = rds.get_paginator('describe_db_instances')
    for page in paginator.paginate():
        instances.extend(page['DBInstances'])
    return instances


def get_all_db_clusters(rds):
    """Fetch all DB clusters using pagination."""
    clusters = []
    paginator = rds.get_paginator('describe_db_clusters')
    for page in paginator.paginate():
        clusters.extend(page['DBClusters'])
    return clusters


def discover_and_sync(rds, elbv2, target_type, target_port):
    """Discovery mode: find RDS resources tagged with place_into_target_group and sync their IPs."""
    TAG_KEY = 'place_into_target_group'

    all_instances = get_all_db_instances(rds)
    all_clusters = get_all_db_clusters(rds)

    # target_group_arn -> set of IPs
    tg_ips = defaultdict(set)

    # Track which instances belong to a cluster so we skip them in the standalone pass
    clustered_instance_ids = set()
    for cluster in all_clusters:
        for member in cluster.get('DBClusterMembers', []):
            clustered_instance_ids.add(member['DBInstanceIdentifier'])

    # Process clusters
    for cluster in all_clusters:
        cluster_arn = cluster['DBClusterArn']
        tags_response = rds.list_tags_for_resource(ResourceName=cluster_arn)
        tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagList', [])}

        tg_arn = tags.get(TAG_KEY)
        if not tg_arn:
            continue

        cluster_id = cluster['DBClusterIdentifier']
        print(f"Discovery: found cluster {cluster_id} tagged for target group {tg_arn}")

        ips = handle_aurora_cluster(rds, cluster, target_type, all_instances=all_instances)
        tg_ips[tg_arn].update(ips)

    # Process standalone instances (not part of any cluster)
    for instance in all_instances:
        instance_id = instance['DBInstanceIdentifier']
        if instance_id in clustered_instance_ids:
            continue

        instance_arn = instance['DBInstanceArn']
        tags_response = rds.list_tags_for_resource(ResourceName=instance_arn)
        tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagList', [])}

        tg_arn = tags.get(TAG_KEY)
        if not tg_arn:
            continue

        print(f"Discovery: found standalone instance {instance_id} tagged for target group {tg_arn}")

        ips = handle_single_instance(instance, target_type)
        tg_ips[tg_arn].update(ips)

    # Sync each target group
    results = []
    for tg_arn, ips in tg_ips.items():
        try:
            sync_target_group(elbv2, tg_arn, ips, target_port)
            results.append(f"Synced {tg_arn} with {list(ips)}")
        except Exception as e:
            print(f"Error syncing target group {tg_arn}: {e}")
            results.append(f"Error syncing {tg_arn}: {e}")

    return {
        'statusCode': 200,
        'body': f'Discovery mode completed. {"; ".join(results)}'
    }
