"""
GymVault - AWS Resources Setup Utility
Automatically provisions S3 bucket, KMS key, SNS topic, and Secrets Manager config.
Requires AWS CLI credentials to be configured (aws configure).
"""

import os
import sys
import json
import logging
import boto3
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load local .env file
load_dotenv()

def run_setup():
    logger.info("=" * 60)
    logger.info("  GymVault - AWS Resources Setup Utility  ")
    logger.info("=" * 60)

    # 1. Initialize AWS clients
    region = os.getenv("AWS_REGION", "us-east-1")
    logger.info(f"Initializing AWS clients for region: {region}...")
    try:
        kms = boto3.client("kms", region_name=region)
        s3 = boto3.client("s3", region_name=region)
        sns = boto3.client("sns", region_name=region)
        secrets = boto3.client("secretsmanager", region_name=region)
    except Exception as e:
        logger.error(f"Failed to initialize boto3 clients. Is AWS CLI configured? Error: {e}")
        sys.exit(1)

    # 2. KMS Key Setup
    kms_key_arn = os.getenv("KMS_KEY_ARN", "")
    if not kms_key_arn:
        logger.info("Creating a new KMS Customer Managed Key...")
        try:
            response = kms.create_key(
                Description="GymVault Customer Managed Key for S3 SSE-KMS",
                KeyUsage="ENCRYPT_DECRYPT",
                CustomerMasterKeySpec="SYMMETRIC_DEFAULT"
            )
            kms_key_arn = response["KeyMetadata"]["Arn"]
            logger.info(f"✅ KMS Key Created: {kms_key_arn}")
            
            # Create Alias
            alias_name = "alias/gymvault-key"
            try:
                kms.create_alias(
                    AliasName=alias_name,
                    TargetKeyId=kms_key_arn
                )
                logger.info(f"✅ KMS Key Alias Created: {alias_name}")
            except kms.exceptions.AlreadyExistsException:
                logger.warning(f"Alias {alias_name} already exists. Updating target...")
                kms.update_alias(
                    AliasName=alias_name,
                    TargetKeyId=kms_key_arn
                )
        except Exception as e:
            logger.error(f"Failed to create KMS key: {e}")
            sys.exit(1)
    else:
        logger.info(f"Using existing KMS key: {kms_key_arn}")

    # 3. S3 Bucket Setup
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not bucket_name:
        logger.error("S3_BUCKET_NAME is not set in .env. Please define a globally unique bucket name in .env.")
        sys.exit(1)
        
    logger.info(f"Creating S3 Bucket: {bucket_name}...")
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        logger.info(f"✅ S3 Bucket Created: {bucket_name}")
        
        # Configure Default Encryption using SSE-KMS
        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": kms_key_arn
                        },
                        "BucketKeyEnabled": True
                    }
                ]
            }
        )
        logger.info("✅ S3 Bucket Default Encryption enabled with KMS key")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        logger.info("S3 Bucket already exists and is owned by you. Proceeding...")
    except Exception as e:
        logger.error(f"Failed to create S3 bucket: {e}")
        sys.exit(1)

    # 4. SNS Topic Setup
    sns_topic_arn = os.getenv("SNS_TOPIC_ARN", "")
    if not sns_topic_arn:
        logger.info("Creating SNS topic...")
        try:
            response = sns.create_topic(Name="gymvault-notifications")
            sns_topic_arn = response["TopicArn"]
            logger.info(f"✅ SNS Topic Created: {sns_topic_arn}")
            
            # Subscribe admin email if configured
            gym_email = os.getenv("GYM_EMAIL", "admin@gymvault.com")
            logger.info(f"Subscribing email {gym_email} to SNS topic...")
            sns.subscribe(
                TopicArn=sns_topic_arn,
                Protocol="email",
                Endpoint=gym_email
            )
            logger.info("✅ Subscription request sent. Please check your inbox and confirm subscription.")
        except Exception as e:
            logger.error(f"Failed to create SNS topic: {e}")
            sys.exit(1)
    else:
        logger.info(f"Using existing SNS topic: {sns_topic_arn}")

    # 5. Secrets Manager Setup
    secret_name = "gymvault/config"
    secret_values = {
        "mongodb_uri": "mongodb://localhost:27017/gymvault", # Local placeholder (update during EC2 deployment)
        "mongodb_db_name": os.getenv("MONGODB_DB_NAME", "gymvault"),
        "s3_bucket_name": bucket_name,
        "s3_region": region,
        "kms_key_arn": kms_key_arn,
        "sns_topic_arn": sns_topic_arn,
        "gym_name": os.getenv("GYM_NAME", "GymVault Fitness Center"),
        "gym_email": os.getenv("GYM_EMAIL", "admin@gymvault.com"),
        "alert_days_before": str(os.getenv("ALERT_DAYS_BEFORE", "7"))
    }
    
    logger.info(f"Storing configuration in AWS Secrets Manager: {secret_name}...")
    try:
        secrets.create_secret(
            Name=secret_name,
            Description="GymVault application configurations",
            SecretString=json.dumps(secret_values)
        )
        logger.info("✅ Secret CREATED successfully in Secrets Manager!")
    except secrets.exceptions.ResourceExistsException:
        logger.warning("Secret already exists. Updating secret value...")
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(secret_values)
        )
        logger.info("✅ Secret UPDATED successfully in Secrets Manager!")
    except Exception as e:
        logger.error(f"Failed to save secrets: {e}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🎉 AWS Resource Setup Completed Successfully!")
    logger.info("Make sure to update MONGODB_URI in secrets manager when deploying to EC2.")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_setup()
