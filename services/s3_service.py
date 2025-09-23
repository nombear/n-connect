import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config.settings import Config
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
            self.bucket_name = Config.S3_BUCKET_NAME
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"Error initializing S3 client: {e}")
            raise

    def upload_text_file(self, content, file_key, content_type='text/plain'):
        """Upload text content to S3 bucket"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=content,
                ContentType=content_type
            )
            logger.info(f"Successfully uploaded {file_key} to S3")
            return True
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def upload_json_file(self, data, file_key):
        """Upload JSON data to S3 bucket"""
        try:
            json_content = json.dumps(data, indent=2, default=str)
            return self.upload_text_file(json_content, file_key, 'application/json')
        except Exception as e:
            logger.error(f"Error uploading JSON to S3: {e}")
            raise

    def download_file(self, file_key):
        """Download file content from S3 bucket"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            content = response['Body'].read().decode('utf-8')
            return content
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"File {file_key} not found in S3")
                return None
            logger.error(f"Error downloading file from S3: {e}")
            raise

    def list_files(self, prefix=''):
        """List files in S3 bucket with optional prefix filter"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag']
                    })

            return files
        except ClientError as e:
            logger.error(f"Error listing files in S3: {e}")
            raise

    def delete_file(self, file_key):
        """Delete file from S3 bucket"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            logger.info(f"Successfully deleted {file_key} from S3")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            raise

    def file_exists(self, file_key):
        """Check if file exists in S3 bucket"""
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence: {e}")
            raise

    def generate_presigned_url(self, file_key, expiration=3600):
        """Generate a presigned URL for file access"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    def create_backup_filename(self, original_name, page_id):
        """Create a backup filename with timestamp"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"notion_backups/{page_id}_{timestamp}_{original_name}"

    def get_files_grouped_by_subfolder(self, prefix=''):
        """Get files grouped by their immediate subfolder"""
        try:
            files = self.list_files(prefix)
            folders = {}

            for file in files:
                # Remove the prefix to get relative path
                relative_path = file['key'][len(prefix):] if file['key'].startswith(prefix) else file['key']

                # Skip files directly in the prefix directory (no subfolder)
                if '/' not in relative_path.strip('/'):
                    continue

                # Get the first folder in the path
                folder_name = relative_path.strip('/').split('/')[0]
                folder_path = f"{prefix.rstrip('/')}/{folder_name}" if prefix else folder_name

                if folder_path not in folders:
                    folders[folder_path] = []

                folders[folder_path].append(file)

            return folders

        except ClientError as e:
            logger.error(f"Error grouping files by subfolder: {e}")
            raise