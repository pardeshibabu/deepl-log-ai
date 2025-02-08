from bson import ObjectId
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.log_model import ElkLog, LogDocument, ErrorLog, BatchAnalysis, BatchResult, AnalysisBatch
from pymongo import MongoClient, ASCENDING, IndexModel

class LogRepository:
    def __init__(self, db_uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        
        # Drop existing index if exists
        try:
            self.collection.drop_index("_source.@timestamp_1__source.message_1")
        except:
            pass

        # Create new index with partial filter
        self.collection.create_index(
            [
                ("_source.@timestamp", ASCENDING),
                ("_source.message", ASCENDING)
            ],
            unique=True,
            partialFilterExpression={
                "_source.@timestamp": {"$exists": True},
                "_source.message": {"$exists": True}
            }
        )

    def log_exists(self, timestamp: datetime, message: str) -> bool:
        """Check if log already exists"""
        return self.collection.count_documents({
            "_source.@timestamp": timestamp,
            "_source.message": message
        }) > 0

    def save_log(self, log: ElkLog) -> str:
        """Save log with upsert to avoid duplicates"""
        log_dict = log.model_dump(exclude={'id'})
        result = self.collection.update_one(
            {
                "_source.@timestamp": log.source.timestamp,
                "_source.message": log.source.message
            },
            {"$setOnInsert": log_dict},
            upsert=True
        )
        return str(result.upserted_id) if result.upserted_id else None

    def get_unanalyzed_logs(self) -> List[ElkLog]:
        logs = self.collection.find({"analyzed": True})
        return [ElkLog(**{**log, "_id": str(log["_id"])}) for log in logs]

    def update_log(self, log_id: str, update_data: dict):
        self.collection.update_one(
            {"_id": ObjectId(log_id)},
            {"$set": update_data}
        )

    def update_log_analysis(self, log_id: str, analysis: dict):
        """Store AI analysis results"""
        print(f"Storing analysis for log {log_id}")
        print(f"Analysis data: {analysis}")
        
        update_data = {
            "analyzed": True,
            "ai_analysis": {
                "timestamp": analysis["timestamp"],
                "error_message": analysis["error_message"],
                "analysis": analysis["analysis"],
                "priority": analysis.get("priority", "MEDIUM"),
                "needs_immediate_attention": analysis.get("needs_immediate_attention", False)
            }
        }
        
        result = self.collection.update_one(
            {"_id": ObjectId(log_id)},
            {"$set": update_data}
        )
        
        print(f"Update result: matched={result.matched_count}, modified={result.modified_count}")
        
        # Verify the update
        updated_doc = self.collection.find_one({"_id": ObjectId(log_id)})
        print(f"Updated document: {updated_doc}")

    def get_analyzed_logs(self) -> List[LogDocument]:
        """Get all analyzed logs"""
        # Add count of all documents
        total_docs = self.collection.count_documents({})
        print(f"Total documents in collection: {total_docs}")
        
        # Add count of analyzed documents
        analyzed_count = self.collection.count_documents({"errors": {"$exists": True, "$ne": []}})
        print(f"Total documents with errors: {analyzed_count}")
        
        logs = self.collection.find({"errors": {"$exists": True, "$ne": []}}).sort("last_analyzed", -1)
        return [LogDocument(**log) for log in logs]

    def get_analyzed_log(self, log_id: str) -> Optional[LogDocument]:
        """Get a single analyzed log by ID"""
        log = self.collection.find_one({
            "_id": ObjectId(log_id),
            "errors": {"$exists": True, "$ne": []}
        })
        
        if not log:
            return None
        
        log["_id"] = str(log["_id"])
        return LogDocument(**log)

    def save_error_and_analysis(self, log: ElkLog, analysis: dict) -> str:
        """Save error and its analysis in the document"""
        error_log = {
            "timestamp": log.source.timestamp,
            "message": log.source.message,
            "level": log.source.msg.level_name,
            "host": log.source.host.hostname,
            "analysis": {
                "timestamp": analysis["timestamp"],
                "error_message": analysis["error_message"],
                "analysis": analysis["analysis"],
                "severity": analysis.get("severity", "MEDIUM"),
                "suggestions": analysis.get("suggestions", []),
                "resolution_steps": analysis.get("resolution_steps", []),
                "needs_immediate_attention": analysis.get("needs_immediate_attention", False)
            }
        }

        # Update or create document
        result = self.collection.update_one(
            {
                "_source.host.hostname": log.source.host.hostname,
                "_source.@timestamp": {
                    "$gte": log.source.timestamp.replace(hour=0, minute=0, second=0),
                    "$lt": (log.source.timestamp.replace(hour=0, minute=0, second=0) + timedelta(days=1))
                }
            },
            {
                "$push": {"errors": error_log},
                "$inc": {
                    "total_errors": 1,
                    "critical_errors": 1 if log.source.msg.level_name == "ERROR" else 0
                },
                "$set": {
                    "last_analyzed": datetime.utcnow(),
                    "_source": log.model_dump(exclude={'id'})["source"]
                },
                "$setOnInsert": {"created_at": datetime.utcnow()}
            },
            upsert=True
        )
        
        return str(result.upserted_id) if result.upserted_id else None

    def get_error_summary(self, host: Optional[str] = None, days: int = 1) -> List[LogDocument]:
        """Get error summary with AI analysis"""
        query = {}
        if host:
            query["_source.host.hostname"] = host
        
        if days:
            query["_source.@timestamp"] = {
                "$gte": datetime.utcnow() - timedelta(days=days)
            }

        documents = self.collection.find(query).sort("last_analyzed", -1)
        return [LogDocument(**doc) for doc in documents]

    def save_batch_analysis(self, logs: List[ElkLog], analyses: List[dict], request_id: str) -> str:
        """Save all logs and analyses in a single document"""
        print(f"Saving batch analysis with request ID: {request_id}")
        
        batch_doc = {
            "type": "batch_analysis",
            "timestamp": datetime.utcnow(),
            "request_id": request_id,
            "logs": [log.model_dump() for log in logs],
            "analysis_results": analyses,
            "total_errors": len(logs),
            "critical_errors": sum(1 for log in logs if log.source.msg.level_name == "ERROR"),
        }
        
        print(f"Document to insert: {batch_doc}")
        result = self.collection.insert_one(batch_doc)
        inserted_id = str(result.inserted_id)
        print(f"Inserted document with ID: {inserted_id}")
        
        # Verify the insert
        saved_doc = self.collection.find_one({"_id": result.inserted_id})
        print(f"Saved document: {saved_doc}")
        
        return inserted_id

    def get_batch_analysis(self, batch_id: str) -> Optional[BatchAnalysis]:
        """Get analysis for a specific batch"""
        try:
            print(f"Looking for batch with ID: {batch_id}")
            
            # First check if document exists at all
            doc = self.collection.find_one({"_id": ObjectId(batch_id)})
            if not doc:
                print("No document found with this ID")
                return None
            
            print(f"Found document: {doc}")
            
            # Now check with type filter
            doc = self.collection.find_one({
                "_id": ObjectId(batch_id),
                "type": "batch_analysis"
            })
            
            if not doc:
                print("Document exists but is not a batch analysis")
                return None
            
            print("Converting document to BatchAnalysis")
            doc["_id"] = str(doc["_id"])
            return BatchAnalysis(**doc)
            
        except Exception as e:
            print(f"Error fetching batch analysis: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(traceback.format_exc())
            return None

    def save_analysis_batch(self, logs: List[ElkLog], analyses: List[dict]) -> str:
        """Save logs with their AI analysis"""
        doc = {
            "timestamp": datetime.utcnow(),
            "analyses": [
                {
                    "timestamp": datetime.utcnow(),
                    "log": log.model_dump(),
                    "error_message": analysis["error_message"],
                    "analysis": analysis["analysis"],
                    "suggestions": analysis["suggestions"],
                    "severity": analysis["severity"],
                    "resolution_steps": analysis["resolution_steps"]
                }
                for log, analysis in zip(logs, analyses)
            ],
            "total_errors": len(logs)
        }
        
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def get_analysis(self, batch_id: str) -> Optional[BatchResult]:
        """Get analysis results"""
        doc = self.collection.find_one({"_id": ObjectId(batch_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            return BatchResult(**doc)
        return None

    def save_batch(self, logs: List[ElkLog], analyses: List[dict]) -> str:
        """Save logs and their analyses in a single document"""
        doc = {
            "timestamp": datetime.utcnow(),
            "logs": [log.model_dump() for log in logs],
            "analyses": analyses,  # Store the raw AI analyses as they come
            "total_errors": len(logs)
        }
        
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def get_batch(self, batch_id: str) -> Optional[AnalysisBatch]:
        """Get a batch by ID"""
        try:
            doc = self.collection.find_one({"_id": ObjectId(batch_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return AnalysisBatch(**doc)
            return None
        except Exception as e:
            print(f"Error getting batch: {e}")
            return None

    def get_latest_with_response(self):
        """
        Get the latest log entry that has a response
        """
        try:
            return self.collection.find_one({
                "response": {"$exists": True}
            }).sort("created_at", -1)
        except Exception as e:
            print(f"Error fetching latest log with response: {str(e)}")
            return None