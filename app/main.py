from fastapi import FastAPI, Request, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.services.log_service import LogService
from app.repositories.log_repository import LogRepository
from app.models.log_model import ElkLog, LogDocument
from app.utils.setup_static import setup_static_directory
from app.services.ai_service import AIService
from dotenv import load_dotenv
import os
from typing import List, Optional
from fastapi.responses import HTMLResponse
from uuid import uuid4
import logging
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import json

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables at the start
load_dotenv()

# Print for debugging
print(f"OpenAI API Key: {os.getenv('OPENAI_API_KEY', 'Not found')[:10]}...")

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Ensure static directory exists
static_dir = setup_static_directory()

# Set up static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Set up templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Initialize dependencies
log_repository = LogRepository(
    db_uri=os.getenv("MONGODB_URI"),
    db_name="logs_db",
    collection_name="logs"
)
log_service = LogService(log_repository)
ai_service = AIService(api_key=os.getenv("OPENAI_API_KEY"))

# Add after existing imports
logger = logging.getLogger(__name__)

@app.get("/")
async def root(request: Request):
    """Render the welcome page with file upload interface"""
    analysis_response = None
    try:
        # Get the latest analysis response from your service
        analysis_response = ai_service.get_latest_response()  # You'll need to implement this method
    except Exception as e:
        logger.error(f"Error fetching analysis response: {str(e)}")
    
    return templates.TemplateResponse(
        "welcome.html", 
        {
            "request": request,
            "page_title": "Log Analyzer",
            "analysis_response": analysis_response
        }
    )

@app.post("/receive-logs")
async def receive_logs(logs: List[ElkLog]):
    """Process logs and store analysis"""
    try:
        batch_id = await log_service.analyze_and_save_batch(logs, ai_service)
        if batch_id:
            return {
                "message": "Analysis complete",
                "batch_id": batch_id,
                "elk_ids": [log.elk_id for log in logs if log.elk_id]
            }
        return {"message": "No errors to analyze"}
    except Exception as e:
        logger.error(f"Error processing logs: {e}")
        return {"error": str(e)}

@app.get("/analyze/{batch_id}")
async def get_analysis(batch_id: str):
    """Get analysis results as JSON"""
    try:
        batch = log_service.get_batch_analysis(batch_id)
        if not batch:
            return {"error": "Analysis not found"}

        return {
            "timestamp": batch.timestamp.isoformat(),
            "total_errors": batch.total_errors,
            "analyses": [
                {
                    "timestamp": analysis["timestamp"],
                    "error_type": analysis["error_type"],
                    "error_message": analysis["error_message"],
                    "file_location": analysis["file_location"],
                    "problematic_code": analysis.get("problematic_code"),
                    "suggested_fix": analysis.get("suggested_fix"),
                    "status_code": analysis.get("status_code", 500),
                    "severity": analysis["severity"],
                    "impact": analysis["impact"],
                    "immediate_actions": analysis["immediate_actions"],
                    "resolution_steps": analysis["resolution_steps"],
                    "needs_immediate_attention": analysis["needs_immediate_attention"]
                }
                for analysis in batch.analyses
            ]
        }
        
    except Exception as e:
        print(f"Error getting analysis: {e}")
        return {"error": str(e)}

@app.post("/analyze-prompt")
async def analyze_prompt(request: Request):
    """Analyze custom prompt and return AI response"""
    try:
        body = await request.json()
        prompt = body.get("prompt")
        generic_message = body.get("generic_message")
        
        if not prompt:
            return {"error": "Prompt is required"}

        if generic_message is not None:
            analysis = await ai_service.analyze_custom_prompt(prompt, {
                "message": generic_message if isinstance(generic_message, str) 
                          else json.dumps(generic_message, indent=2),
                "context": {},
                "data_type": type(generic_message).__name__
            })
            
            # Format the response nicely
            if isinstance(analysis, dict):
                formatted_analysis = json.dumps(analysis, indent=2)
            else:
                formatted_analysis = str(analysis)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "analysis": formatted_analysis
            }
            
    except Exception as e:
        logger.error(f"Error in analyze-prompt: {str(e)}")
        return {"error": str(e)}

def get_request_type(generic_message, elk_logs):
    """Helper to determine request type for logging"""
    if generic_message is not None:
        return f"Generic ({type(generic_message).__name__})"
    elif elk_logs:
        return f"ELK Logs ({len(elk_logs)} logs)"
    return "Context-based"

@app.post("/analyze-prompt-with-logs")
async def analyze_prompt_with_logs(
    request: Request,
    logs: List[ElkLog] = Body(..., embed=True),
    prompt: str = Body(..., embed=True)
):
    """Analyze custom prompt with ELK logs"""
    try:
        # Create context from logs
        logs_context = {
            "logs": [
                {
                    "message": log.source.message,
                    "timestamp": log.source.timestamp.isoformat(),
                    "level": log.source.msg.level_name,
                    "file": log.source.log.get("file", {}).get("path", "Unknown"),
                    "elk_id": log.elk_id
                }
                for log in logs
            ]
        }
        
        # Analyze with AI and save batch
        batch_id = await log_service.analyze_and_save_batch(logs, ai_service, custom_prompt=prompt)
        
        if batch_id:
            return {
                "message": "Analysis complete",
                "batch_id": batch_id,
                "elk_ids": [log.elk_id for log in logs if log.elk_id]
            }
        return {"message": "No errors to analyze"}
        
    except Exception as e:
        logger.error(f"Error analyzing prompt with logs: {e}")
        return {"error": str(e)}