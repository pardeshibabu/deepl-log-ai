from elasticsearch import Elasticsearch
from typing import List
from datetime import datetime, timedelta
from app.models.log_model import ElkLog

class ElkService:
    def __init__(self, elk_url: str, index_pattern: str = "sr-api-internal-laravel-*"):
        self.client = Elasticsearch(elk_url)
        self.index_pattern = index_pattern

    def get_recent_logs(self, minutes: int = 5) -> List[dict]:
        """Get logs from the last n minutes"""
        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": f"now-{minutes}m",
                                "lte": "now"
                            }
                        }
                    }
                ]
            }
        }

        response = self.client.search(
            index=self.index_pattern,
            query=query,
            size=100,  # Adjust size as needed
            sort=[{"@timestamp": {"order": "desc"}}]
        )

        return [hit for hit in response['hits']['hits']] 