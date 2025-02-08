from app.repositories.log_repository import LogRepository
from app.models.log_model import ElkLog, LogDocument, BatchAnalysis, AnalysisBatch
from typing import List, Optional
from app.services.ai_service import AIService
import httpx
from datetime import datetime
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogService:
    def __init__(self, log_repository: LogRepository):
        self.log_repository = log_repository
        self.webhook_url = "https://multichannel-channels-partnerships-qa-api.kartrocket.com/v1/byte-fusion/ai-webhook"
        self.webhook_timeout = 30

    def save_log(self, log: ElkLog) -> str:
        return self.log_repository.save_log(log)

    def get_unanalyzed_logs(self) -> List[ElkLog]:
        return self.log_repository.get_unanalyzed_logs()

    def mark_log_as_analyzed(self, log_id: str, ai_response: str):
        update_data = {
            "analyzed": True,
            "ai_response": ai_response
        }
        self.log_repository.update_log(log_id, update_data)

    def store_analysis(self, log_id: str, analysis: dict):
        """Store AI analysis results"""
        self.log_repository.update_log_analysis(log_id, analysis)

    def get_analyzed_logs(self) -> List[LogDocument]:
        """Get analyzed logs"""
        return self.log_repository.get_analyzed_logs()

    def get_analyzed_log(self, log_id: str) -> Optional[LogDocument]:
        """Get a single analyzed log by ID"""
        return self.log_repository.get_analyzed_log(log_id)

    def save_error_and_analysis(self, log: ElkLog, analysis: dict) -> str:
        """Save error with analysis"""
        return self.log_repository.save_error_and_analysis(log, analysis)

    def save_batch_analysis(self, logs: List[ElkLog], analyses: List[dict], request_id: str) -> str:
        """Save batch analysis"""
        return self.log_repository.save_batch_analysis(logs, analyses, request_id)

    def get_batch_analysis(self, batch_id: str) -> Optional[AnalysisBatch]:
        """Get analysis results"""
        return self.log_repository.get_batch(batch_id)

    async def send_webhook_notification(self, analysis_data: dict, batch_id: str, elk_ids: List[str]):
        """Send webhook notification with analysis summary"""
        try:
            # Prepare webhook payload
            webhook_payload = {
                "data": {
                    "timestamp": analysis_data["timestamp"],
                    "batch_id": batch_id,
                    "elk_ids": elk_ids,
                    "total_errors": analysis_data["total_errors"],
                    "analyses": analysis_data["analyses"],
                    "summary": {
                        "high_severity": sum(1 for a in analysis_data["analyses"] if a["severity"] == "HIGH"),
                        "medium_severity": sum(1 for a in analysis_data["analyses"] if a["severity"] == "MEDIUM"),
                        "low_severity": sum(1 for a in analysis_data["analyses"] if a["severity"] == "LOW"),
                        "critical_files": [
                            {
                                "file": a["file_location"],
                                "error_type": a["error_type"],
                                "error_message": a["error_message"],
                                "elk_id": a["elk_id"]
                            }
                            for a in analysis_data["analyses"] if a["needs_immediate_attention"]
                        ],
                        "error_types": {}
                    }
                }
            }
            logger.info(f"Sending webhook payload: {webhook_payload}")
            # Send webhook
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    self.webhook_url,
                    json=webhook_payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "LogAnalyzer/1.0"
                    },
                    timeout=self.webhook_timeout
                )
                response.raise_for_status()
                logger.info(f"Webhook sent successfully. Status: {response.status_code}")

        except Exception as e:
            logger.error(f"Error in send_webhook_notification: {str(e)}", exc_info=True)
            raise

    async def analyze_and_save_batch(self, logs: List[ElkLog], ai_service: AIService, custom_prompt: str = None) -> Optional[str]:
        """Analyze logs and save results, then send webhook"""
        try:
            analyses = []
            error_logs = []
            elk_ids = []
            
            logger.info(f"Processing {len(logs)} logs for analysis")
            
            for log in logs:
                # Debug logging
                logger.info(f"Processing log ID: {log.id}")
                logger.info(f"Source data: {log.source}")
                
                # Check for errors in both source and event.original
                is_error = False
                source_level = log.source.get("level_name")
                
                logger.info(f"Source level: {source_level}")
                
                if source_level in ["ERROR", "EMERGENCY"]:
                    is_error = True
                    logger.info("Error found in source level")
                
                # Always try to parse event.original for additional context
                try:
                    event_data = json.loads(log.source.get("event", {}).get("original", "{}"))
                    logger.info(f"Event data: {event_data}")
                    
                    if event_data.get("level_name") == "ERROR" or event_data.get("level", 0) >= 400:
                        is_error = True
                        logger.info("Error found in event data")
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse event.original for log {log.id}: {str(e)}")

                if is_error:
                    logger.info(f"Processing error log: {log.source.get('message')}")
                    # Use custom prompt if provided
                    if custom_prompt:
                        analysis = await ai_service.analyze_custom_prompt(custom_prompt, {"log": log.model_dump()})
                    else:
                        analysis = ai_service.analyze_log(log)
                    
                    analysis["elk_id"] = log.elk_id
                    analyses.append(analysis)
                    error_logs.append(log)
                    if log.elk_id:
                        elk_ids.append(log.elk_id)
                    logger.info(f"Added error log with elk_id: {log.elk_id}")
                else:
                    logger.info("Log is not an error, skipping")
            
            logger.info(f"Total error logs found: {len(error_logs)}")
            logger.info(f"Total analyses: {len(analyses)}")
            logger.info(f"Total elk_ids: {len(elk_ids)}")
            
            if error_logs:
                logger.info(f"Found {len(error_logs)} errors to analyze")
                batch_id = self.log_repository.save_batch(error_logs, analyses)
                
                # Prepare and send webhook
                analysis_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "total_errors": len(error_logs),
                    "analyses": analyses
                }
                
                try:
                    await self.send_webhook_notification(analysis_data, batch_id, elk_ids)
                except Exception as webhook_error:
                    logger.error(f"Webhook notification failed but batch was saved. Error: {str(webhook_error)}")
                
                return batch_id
            
            logger.info("No errors found to analyze")
            return None
            
        except Exception as e:
            logger.error(f"Error in analyze_and_save_batch: {str(e)}", exc_info=True)
            return None