from services.notion_service import NotionService
from services.workday_service import WorkdayService
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class NotionWorkdayIntegration:
    def __init__(self):
        self.notion_service = NotionService()
        self.workday_service = WorkdayService()
