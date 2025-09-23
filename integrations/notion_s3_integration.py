from services.notion_service import NotionService
from services.s3_service import S3Service
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class NotionS3Integration:
    def __init__(self):
        self.notion_service = NotionService()
        self.s3_service = S3Service()

    def backup_page_to_s3(self, page_id):
        """Backup a Notion page to S3 as both JSON and text"""
        try:
            # Get page content from Notion
            page_content = self.notion_service.get_page_content(page_id)
            text_content = self.notion_service.export_page_to_text(page_id)

            # Generate filenames
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_key = f"notion_backups/{page_id}/page_{timestamp}.json"
            text_key = f"notion_backups/{page_id}/page_{timestamp}.txt"

            # Upload to S3
            self.s3_service.upload_json_file(page_content, json_key)
            self.s3_service.upload_text_file(text_content, text_key)

            logger.info(f"Successfully backed up page {page_id} to S3")
            return {
                'page_id': page_id,
                'json_backup': json_key,
                'text_backup': text_key,
                'timestamp': timestamp
            }

        except Exception as e:
            logger.error(f"Error backing up page {page_id}: {e}")
            raise

    def backup_all_pages(self):
        """Backup all pages from the Notion database to S3"""
        try:
            pages = self.notion_service.get_database_pages()
            backup_results = []

            for page in pages:
                page_id = page['id']
                result = self.backup_page_to_s3(page_id)
                backup_results.append(result)

            # Create a summary file
            summary = {
                'backup_date': datetime.now().isoformat(),
                'total_pages': len(backup_results),
                'backups': backup_results
            }

            summary_key = f"notion_backups/backup_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.s3_service.upload_json_file(summary, summary_key)

            logger.info(f"Successfully backed up {len(backup_results)} pages")
            return summary

        except Exception as e:
            logger.error(f"Error during bulk backup: {e}")
            raise

    def restore_page_from_s3(self, s3_key):
        """Restore a page from S3 backup (placeholder for future implementation)"""
        try:
            # Download the JSON backup
            content = self.s3_service.download_file(s3_key)
            if not content:
                raise ValueError(f"Backup file {s3_key} not found")

            page_data = json.loads(content)

            # Note: Actual restoration would require creating a new page
            # and reconstructing the blocks. This is a complex operation
            # that depends on your specific needs.

            logger.info(f"Downloaded backup from {s3_key}")
            return page_data

        except Exception as e:
            logger.error(f"Error restoring from {s3_key}: {e}")
            raise

    def sync_page_to_s3(self, page_id, auto_backup=True):
        """Sync a specific page to S3 with optional auto-backup"""
        try:
            if auto_backup:
                # Create backup first
                backup_result = self.backup_page_to_s3(page_id)

            # Get current page content
            text_content = self.notion_service.export_page_to_text(page_id)

            # Upload current version
            current_key = f"notion_sync/{page_id}/current.txt"
            self.s3_service.upload_text_file(text_content, current_key)

            result = {
                'page_id': page_id,
                'synced_file': current_key,
                'timestamp': datetime.now().isoformat()
            }

            if auto_backup:
                result['backup'] = backup_result

            logger.info(f"Successfully synced page {page_id}")
            return result

        except Exception as e:
            logger.error(f"Error syncing page {page_id}: {e}")
            raise

    def list_backups(self, page_id=None):
        """List all backups, optionally filtered by page_id"""
        try:
            prefix = f"notion_backups/{page_id}/" if page_id else "notion_backups/"
            files = self.s3_service.list_files(prefix)

            backups = []
            for file in files:
                if file['key'].endswith('.json'):
                    backups.append({
                        'key': file['key'],
                        'size': file['size'],
                        'last_modified': file['last_modified']
                    })

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            raise

    def get_backup_summary(self):
        """Get a summary of all backup operations"""
        try:
            summary_files = self.s3_service.list_files("notion_backups/backup_summary_")
            summaries = []

            for file in summary_files:
                content = self.s3_service.download_file(file['key'])
                if content:
                    summary_data = json.loads(content)
                    summaries.append(summary_data)

            return sorted(summaries, key=lambda x: x['backup_date'], reverse=True)

        except Exception as e:
            logger.error(f"Error getting backup summary: {e}")
            raise

    def embed_s3_document_in_page(self, page_id, s3_key, link_text=None, include_metadata=True, expiration=3600):
        """Embed an S3 document link in an existing Notion page"""
        try:
            # Check if S3 file exists
            if not self.s3_service.file_exists(s3_key):
                raise ValueError(f"S3 file {s3_key} does not exist")

            # Generate presigned URL
            presigned_url = self.s3_service.generate_presigned_url(s3_key, expiration)

            # Get file metadata if requested
            description = None
            if include_metadata:
                files = self.s3_service.list_files(s3_key)
                if files:
                    file_info = files[0]
                    size_mb = round(file_info['size'] / (1024 * 1024), 2)
                    description = f"File size: {size_mb} MB | Last modified: {file_info['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}"

            # Add the link to the Notion page
            result = self.notion_service.add_s3_link_to_page(
                page_id=page_id,
                s3_url=presigned_url,
                link_text=link_text or s3_key.split('/')[-1],
                description=description
            )

            logger.info(f"Successfully embedded S3 document {s3_key} in page {page_id}")
            return {
                'page_id': page_id,
                's3_key': s3_key,
                'presigned_url': presigned_url,
                'link_text': link_text or s3_key.split('/')[-1],
                'expires_in': expiration,
                'metadata': description
            }

        except Exception as e:
            logger.error(f"Error embedding S3 document in page: {e}")
            raise

    def create_notion_page_with_s3_documents(self, title, s3_keys, properties=None, expiration=3600):
        """Create a new Notion page with multiple S3 document links"""
        try:
            # Prepare S3 links data
            s3_links = []
            for s3_key in s3_keys:
                # Check if file exists
                if not self.s3_service.file_exists(s3_key):
                    logger.warning(f"S3 file {s3_key} does not exist, skipping")
                    continue

                # Generate presigned URL
                presigned_url = self.s3_service.generate_presigned_url(s3_key, expiration)

                # Get file metadata
                files = self.s3_service.list_files(s3_key)
                description = None
                if files:
                    file_info = files[0]
                    size_mb = round(file_info['size'] / (1024 * 1024), 2)
                    description = f"File size: {size_mb} MB | Last modified: {file_info['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}"

                s3_links.append({
                    'url': presigned_url,
                    'text': s3_key.split('/')[-1],
                    'description': description
                })

            # Create the Notion page with S3 links
            page = self.notion_service.create_page_with_s3_links(title, s3_links, properties)

            logger.info(f"Successfully created Notion page with {len(s3_links)} S3 documents")
            return {
                'page': page,
                's3_documents': len(s3_links),
                's3_keys': s3_keys,
                'expires_in': expiration
            }

        except Exception as e:
            logger.error(f"Error creating Notion page with S3 documents: {e}")
            raise

    def list_s3_documents_for_notion(self, prefix='', file_extensions=None):
        """List S3 documents that can be embedded in Notion pages"""
        try:
            files = self.s3_service.list_files(prefix)

            # Filter by file extensions if provided
            if file_extensions:
                file_extensions = [ext.lower() for ext in file_extensions]
                files = [f for f in files if any(f['key'].lower().endswith(ext) for ext in file_extensions)]

            # Format for display
            documents = []
            for file in files:
                size_mb = round(file['size'] / (1024 * 1024), 2)
                documents.append({
                    'key': file['key'],
                    'name': file['key'].split('/')[-1],
                    'size_mb': size_mb,
                    'last_modified': file['last_modified'].isoformat(),
                    'extension': file['key'].split('.')[-1].lower() if '.' in file['key'] else 'unknown'
                })

            return documents

        except Exception as e:
            logger.error(f"Error listing S3 documents: {e}")
            raise

    def create_notion_pages_from_s3_folders(self, folder_prefix='', base_title_prefix='', properties=None, expiration=3600):
        """Create separate Notion pages for each subfolder in the specified S3 prefix"""
        try:
            # Get files grouped by subfolder
            folders = self.s3_service.get_files_grouped_by_subfolder(folder_prefix)

            if not folders:
                logger.warning(f"No subfolders found in prefix: {folder_prefix}")
                return {
                    'created_pages': [],
                    'total_folders': 0,
                    'total_files': 0
                }

            created_pages = []
            total_files = 0

            for folder_path, files in folders.items():
                # Generate page title from folder name
                folder_name = folder_path.split('/')[-1]
                page_title = f"{base_title_prefix}{folder_name}" if base_title_prefix else folder_name
                if self.notion_service.page_exists(page_title):
                    raise TypeError(f"Page {page_title} already exists")
                # Prepare S3 links data for this folder
                s3_links = []
                for file in files:
                    s3_key = file['key']

                    # Generate presigned URL
                    presigned_url = self.s3_service.generate_presigned_url(s3_key, expiration)

                    # Get file metadata
                    size_mb = round(file['size'] / (1024 * 1024), 2)
                    description = f"File size: {size_mb} MB | Last modified: {file['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}"

                    s3_links.append({
                        'url': presigned_url,
                        'text': s3_key.split('/')[-1],
                        'description': description
                    })

                # Create the Notion page with S3 links for this folder
                page = self.notion_service.create_page_with_s3_links(page_title, s3_links, properties)

                created_pages.append({
                    'page': page,
                    'folder_path': folder_path,
                    'page_title': page_title,
                    'file_count': len(files),
                    's3_keys': [f['key'] for f in files]
                })

                total_files += len(files)
                logger.info(f"Created page '{page_title}' with {len(files)} files from folder {folder_path}")

            logger.info(f"Successfully created {len(created_pages)} pages from {len(folders)} folders with {total_files} total files")
            return {
                'created_pages': created_pages,
                'total_folders': len(folders),
                'total_files': total_files,
                'expires_in': expiration
            }

        except Exception as e:
            logger.error(f"Error creating Notion pages from S3 folders: {e}")
            raise