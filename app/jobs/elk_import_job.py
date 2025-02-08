from apscheduler.schedulers.blocking import BlockingScheduler
from app.services.elk_service import ElkService
from app.repositories.log_repository import LogRepository
from app.models.log_model import ElkLog
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def import_elk_logs():
    print("Starting ELK log import...")
    
    # Initialize services
    elk_service = ElkService(
        elk_url=os.getenv("ELK_URL", "http://localhost:9200")
    )
    
    log_repository = LogRepository(
        db_uri=os.getenv("MONGODB_URI"),
        db_name="logs_db",
        collection_name="logs"
    )
    
    try:
        # Get recent logs from ELK
        elk_logs = elk_service.get_recent_logs(minutes=5)
        
        # Convert and save to MongoDB
        for log_data in elk_logs:
            try:
                # Create ElkLog model
                log = ElkLog.model_validate(log_data)
                
                # Save to MongoDB if not exists
                if not log_repository.log_exists(log.source.timestamp, log.source.message):
                    log_repository.save_log(log)
                    print(f"Saved log from {log.source.timestamp}")
            except Exception as e:
                print(f"Error processing log: {str(e)}")
                continue
                
        print(f"Imported {len(elk_logs)} logs")
    except Exception as e:
        print(f"Error in import job: {str(e)}")

if __name__ == "__main__":
    print("Starting ELK import job...")
    scheduler = BlockingScheduler()
    scheduler.add_job(import_elk_logs, 'interval', minutes=5)
    scheduler.start() 