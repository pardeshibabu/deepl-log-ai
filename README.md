## Required Software
- **Python 3.8+**
- **MongoDB**
- **OpenAI API Key**

---

## Clone Repository
```bash
git clone <repository-url>
cd log-analysis-system
```

---

## Create Virtual Environment
```bash
python -m venv venv
```

### Activate Virtual Environment
#### For Windows:
```bash
venv\Scripts\activate
```

#### For Unix/MacOS:
```bash
source venv/bin/activate
```

---

## Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Environment Setup
Create a `.env` file and include the following:
```env
MONGODB_URI=mongodb://localhost:27017
OPENAI_API_KEY=your_openai_api_key
```

---

## Start the Server
```bash
uvicorn app.main:app --reload --port 8000
```

---

## Logs
Send logs using the following command:
```bash
curl -X POST http://localhost:8000/receive-logs \
-H "Content-Type: application/json" \
-d '[{
    "index": "logs-2024",
    "type": "_doc",
    "id": "123",
    "elk_id": "elk-123",
    "source": {
        "message": "Error message here",
        "timestamp": "2024-03-21T10:00:00",
        "level": "ERROR"
    }
}]'
```

---

## Analysis
Retrieve analysis for a batch of logs:
```bash
curl http://localhost:8000/analyze/{batch_id}
```
### Example Response
```json
{
    "timestamp": "2024-03-21T12:00:00",
    "batch_id": "67a725dc1594d5e607dc04c7",
    "elk_ids": ["elk-123"],
    "total_errors": 1,
    "summary": {
        "high_severity": 1,
        "medium_severity": 0,
        "low_severity": 0,
        "critical_files": [
            {
                "file": "/path/to/file.php",
                "error_type": "Database Error",
                "error_message": "Connection failed",
                "elk_id": "elk-123"
            }
        ],
        "error_types": {
            "Database Error": 1
        }
    }
}
```

---

## Project Structure
```plaintext
app/
├── main.py              # FastAPI application entry point
├── services/
│   ├── ai_service.py    # GPT-4 integration
│   └── log_service.py   # Log processing logic
├── models/
│   └── log_model.py     # Data models
├── repositories/
│   └── log_repository.py # Database operations
└── templates/
    └── welcome.html     # Web interface template
```

---

## Common Issues and Solutions
### Error: MongoDB connection failed
**Solution:** Ensure MongoDB is running
```bash
mongod --dbpath /path/to/data/db
```

### Error: OpenAI API key invalid
**Solution:** Check `.env` file and API key validity
```bash
echo $OPENAI_API_KEY
```

### Error: Webhook timeout
**Solution:** Check webhook URL and increase timeout
In `log_service.py`:
```python
self.webhook_timeout = 60  # Increase timeout seconds
```

---

## Development Guidelines
### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_ai_service.py
```

### Format Code
```bash
black app/
```

### Check Types
```bash
mypy app/
