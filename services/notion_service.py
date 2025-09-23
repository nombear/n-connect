from notion_client import Client
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class NotionService:
    def __init__(self):
        self.client = Client(auth=Config.NOTION_API_TOKEN)
        self.page_id = Config.NOTION_PAGE_ID

    def get_database_pages(self):
        """Retrieve all pages from the Notion database"""
        try:
            response = self.client.databases.query(database_id=self.database_id)
            return response.get('results', [])
        except Exception as e:
            logger.error(f"Error retrieving pages from Notion: {e}")
            raise

    def get_page_content(self, page_id):
        """Get detailed content of a specific page"""
        try:
            page = self.client.pages.retrieve(page_id=page_id)
            blocks = self.client.blocks.children.list(block_id=page_id)
            return {
                'page': page,
                'blocks': blocks.get('results', [])
            }
        except Exception as e:
            logger.error(f"Error retrieving page content: {e}")
            raise

    def create_page(self, title, properties=None):
        """Create a new page in the database"""
        try:
            page_properties = {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }

            if properties:
                page_properties.update(properties)

            response = self.client.pages.create(
                parent={"page_id": self.page_id},
                properties=page_properties
            )
            return response
        except Exception as e:
            logger.error(f"Error creating page: {e}")
            raise

    def update_page(self, page_id, properties):
        """Update properties of an existing page"""
        try:
            response = self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            return response
        except Exception as e:
            logger.error(f"Error updating page: {e}")
            raise

    def export_page_to_text(self, page_id):
        """Export page content as plain text"""
        try:
            content = self.get_page_content(page_id)
            text_content = []

            # Extract page title
            page = content['page']
            if 'properties' in page and 'Name' in page['properties']:
                title = page['properties']['Name']['title']
                if title:
                    text_content.append(title[0]['text']['content'])

            # Extract block content
            for block in content['blocks']:
                if block['type'] == 'paragraph':
                    rich_text = block['paragraph']['rich_text']
                    for text_item in rich_text:
                        text_content.append(text_item['text']['content'])
                elif block['type'] == 'heading_1':
                    rich_text = block['heading_1']['rich_text']
                    for text_item in rich_text:
                        text_content.append(f"# {text_item['text']['content']}")
                elif block['type'] == 'heading_2':
                    rich_text = block['heading_2']['rich_text']
                    for text_item in rich_text:
                        text_content.append(f"## {text_item['text']['content']}")
                elif block['type'] == 'heading_3':
                    rich_text = block['heading_3']['rich_text']
                    for text_item in rich_text:
                        text_content.append(f"### {text_item['text']['content']}")

            return '\n'.join(text_content)
        except Exception as e:
            logger.error(f"Error exporting page to text: {e}")
            raise

    def add_s3_link_to_page(self, page_id, s3_url, link_text=None, description=None):
        """Add an S3 document link to a Notion page"""
        try:
            # Create the link block
            image_block = {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url" : s3_url
                    },
                    "caption" : [
                        {
                            "type" : "text",
                            "text": {"content": s3_url}
                        }
                    ]
                }
            }

            # Add description if provided
            blocks_to_add = [image_block]
            if description:
                description_block = {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": description
                                }
                            }
                        ]
                    }
                }
                blocks_to_add.append(description_block)

            # Append the blocks to the page
            response = self.client.blocks.children.append(
                block_id=page_id,
                children=blocks_to_add
            )

            logger.info(f"Successfully added S3 link to page {page_id}")
            return response

        except Exception as e:
            logger.error(f"Error adding S3 link to page {page_id}: {e}")
            raise

    def create_page_with_s3_links(self, title, s3_links, properties=None):
        """Create a new page with embedded S3 document links"""
        try:
            # Create the page first
            page = self.create_page(title, properties)
            page_id = page['id']

            # Add each S3 link to the page
            for link_info in s3_links:
                s3_url = link_info['url']
                link_text = link_info.get('text', 'S3 Document')
                description = link_info.get('description')

                self.add_s3_link_to_page(page_id, s3_url, link_text, description)

            logger.info(f"Successfully created page with S3 links: {page_id}")
            return page

        except Exception as e:
            logger.error(f"Error creating page with S3 links: {e}")
            raise

    def search_pages_by_title(self, title):
        """Search for existing pages by title in the current page's children"""
        try:
            # Get all child pages
            response = self.client.blocks.children.list(block_id=self.page_id)
            pages = []

            for block in response.get('results', []):
                if block['type'] == 'child_page':
                    page_id = block['id']
                    page_details = self.client.pages.retrieve(page_id=page_id)

                    # Extract title from page properties
                    page_title = ""
                    if 'properties' in page_details:
                        for prop_name, prop_data in page_details['properties'].items():
                            if prop_data['type'] == 'title':
                                title_parts = prop_data['title']
                                if title_parts:
                                    page_title = title_parts[0]['text']['content']
                                break

                    if page_title.lower() == title.lower():
                        pages.append(page_details)

            return pages

        except Exception as e:
            logger.error(f"Error searching for pages by title: {e}")
            raise

    def page_exists(self, title):
        """Check if a page with the given title already exists"""
        try:
            existing_pages = self.search_pages_by_title(title)
            return len(existing_pages) > 0
        except Exception as e:
            logger.error(f"Error checking if page exists: {e}")
            raise