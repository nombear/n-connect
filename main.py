from flask import Flask, jsonify, request
from services.integration_service import NotionS3Integration
from config.settings import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

try:
    Config.validate_config()
    integration = NotionS3Integration()
except Exception as e:
    logger.error(f"Configuration error: {e}")
    integration = None

@app.route('/')
def index():
    return jsonify({
        'message': 'Notion-S3 Integration API',
        'version': '1.0',
        'endpoints': {
            'backup_page': '/backup/page/<page_id>',
            'backup_all': '/backup/all',
            'sync_page': '/sync/page/<page_id>',
            'list_backups': '/backups',
            'backup_summary': '/backups/summary',
            'embed_s3_document': '/embed/s3/page/<page_id>',
            'create_page_with_s3': '/create/page/s3',
            'list_s3_documents': '/s3/documents'
        }
    })

@app.route('/backup/page/<page_id>', methods=['POST'])
def backup_page(page_id):
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    try:
        result = integration.backup_page_to_s3(page_id)
        return jsonify({
            'success': True,
            'message': f'Page {page_id} backed up successfully',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error backing up page {page_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/backup/all', methods=['POST'])
def backup_all_pages():
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    try:
        result = integration.backup_all_pages()
        return jsonify({
            'success': True,
            'message': f'Successfully backed up {result["total_pages"]} pages',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error during bulk backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/page/<page_id>', methods=['POST'])
def sync_page(page_id):
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    auto_backup = request.json.get('auto_backup', True) if request.json else True

    try:
        result = integration.sync_page_to_s3(page_id, auto_backup)
        return jsonify({
            'success': True,
            'message': f'Page {page_id} synced successfully',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error syncing page {page_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/backups', methods=['GET'])
def list_backups():
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    page_id = request.args.get('page_id')

    try:
        backups = integration.list_backups(page_id)
        return jsonify({
            'success': True,
            'data': backups
        })
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/backups/summary', methods=['GET'])
def backup_summary():
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    try:
        summary = integration.get_backup_summary()
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        logger.error(f"Error getting backup summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/embed/s3/page/<page_id>', methods=['POST'])
def embed_s3_document(page_id):
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    data = request.get_json()
    if not data or 's3_key' not in data:
        return jsonify({'error': 's3_key is required'}), 400

    s3_key = data['s3_key']
    link_text = data.get('link_text')
    include_metadata = data.get('include_metadata', True)
    expiration = data.get('expiration', 3600)

    try:
        result = integration.embed_s3_document_in_page(
            page_id=page_id,
            s3_key=s3_key,
            link_text=link_text,
            include_metadata=include_metadata,
            expiration=expiration
        )
        return jsonify({
            'success': True,
            'message': f'S3 document {s3_key} embedded in page {page_id}',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error embedding S3 document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/create/page/s3', methods=['POST'])
def create_page_with_s3_documents():
    print("Invoking S3 Page Creation")
    print(integration)
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    data = request.get_json()
    if not data or 'title' not in data or 's3_keys' not in data:
        return jsonify({'error': 'title and s3_keys are required'}), 400

    title = data['title']
    s3_keys = data['s3_keys']
    properties = data.get('properties')
    expiration = data.get('expiration', 3600)

    if not isinstance(s3_keys, list):
        return jsonify({'error': 's3_keys must be a list'}), 400

    try:
        result = integration.create_notion_page_with_s3_documents(
            title=title,
            s3_keys=s3_keys,
            properties=properties,
            expiration=expiration
        )
        return jsonify({
            'success': True,
            'message': f'Created page "{title}" with {result["s3_documents"]} S3 documents',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error creating page with S3 documents: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/s3/documents', methods=['GET'])
def list_s3_documents():
    if not integration:
        return jsonify({'error': 'Service not properly configured'}), 500

    prefix = request.args.get('prefix', '')
    extensions = request.args.get('extensions')
    file_extensions = extensions.split(',') if extensions else None

    try:
        documents = integration.list_s3_documents_for_notion(
            prefix=prefix,
            file_extensions=file_extensions
        )
        return jsonify({
            'success': True,
            'data': {
                'documents': documents,
                'count': len(documents),
                'filter': {
                    'prefix': prefix,
                    'extensions': file_extensions
                }
            }
        })
    except Exception as e:
        logger.error(f"Error listing S3 documents: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    app.run(debug=Config.DEBUG)

