import sagemaker
import boto3
import os
import subprocess
from sagemaker.tensorflow import TensorFlow
from sagemaker.serverless import ServerlessInferenceConfig
from sagemaker import get_execution_role
REGION = "us-east-1"

# Create a boto3 session with specified AWS region
boto3.setup_default_session(region_name=REGION)
os.environ['AWS_DEFAULT_REGION'] = REGION
boto3_session = boto3.Session()
sagemaker_session = sagemaker.Session(boto_session=boto3_session)
sagemaker_default_bucket =  sagemaker_session.default_bucket()
sagemaker_role = get_execution_role()
print(sagemaker_role)

# Get the AWS account ID
account_id = boto3.client("sts").get_caller_identity()["Account"]
#bucket_name = f'{account_id}-{REGION}-tampered-image-detection-training'

#copy images folder to S3
subprocess.run(["aws", "s3", "cp", "--recursive", "./images", f"s3://{sagemaker_default_bucket}/tampered-image-train/"], shell=False)

estimator = TensorFlow(
    sagemaker_session = sagemaker_session,
    entry_point='model.py',
    role=sagemaker_role,
    instance_count=1,
    instance_type='ml.m5.4xlarge',
    framework_version='2.1.0',
    py_version='py3',
)

estimator.fit({'train':f's3://{sagemaker_default_bucket}/tampered-image-train/'})

# Configure serverless inference
serverless_config = ServerlessInferenceConfig(
    memory_size_in_mb = 2048,
    max_concurrency = 1,
)

# Deploy
predictor = estimator.deploy(initial_instance_count=1,
                             endpoint_name="document-tampering-detection-v-DEMO",
                             serverless_inference_config=serverless_config)

print("Copy this value:", predictor.endpoint)