from apscheduler.schedulers.blocking import BlockingScheduler
from app.services.log_service import LogService
from app.services.ai_service import AIService
from app.utils.slack_notifier import SlackNotifier
from app.repositories.log_repository import LogRepository
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

def analyze_logs():
    print("Analyzing logs...")
    
    # Initialize services
    log_repository = LogRepository(
        db_uri=os.getenv("MONGODB_URI"),
        db_name="logs_db",
        collection_name="logs"
    )
    log_service = LogService(log_repository)
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"Using API key: {api_key[:10]}...")  # Print first 10 chars for debugging
    ai_service = AIService(api_key)
    # slack_notifier = SlackNotifier()
    
    # Get unanalyzed logs
    logs = log_service.get_unanalyzed_logs()
    
    for log in logs:
        try:
            # Analyze log with AI
            analysis = ai_service.analyze_log(log)
            print(analysis)
            # Update log with analysis
            log_service.mark_log_as_analyzed(log.id, analysis)
            
            # Send notification if critical
            if "error" in log.level.lower():
                # slack_notifier.send_notification(
                #     f"Critical Log Detected!\nSource: {log.source}\nMessage: {log.message}\nAnalysis: {analysis}"
                # )
                print(f"Critical Log Detected!\nSource: {log.source}\nMessage: {log.message}\nAnalysis: {analysis}")
        except Exception as e:
            print(f"Error processing log: {str(e)}")

if __name__ == "__main__":
    print("Starting log analyzer job...")
    analyze_logs()  # Run once immediately
    scheduler = BlockingScheduler()
    scheduler.add_job(analyze_logs, 'interval', minutes=5)
    scheduler.start()