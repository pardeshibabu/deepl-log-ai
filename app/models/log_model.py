from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List, Any

class Agent(BaseModel):
    ephemeral_id: str
    name: str
    id: str
    type: str
    version: str

class Host(BaseModel):
    id: str
    hostname: str
    containerized: bool
    mac: List[str]
    name: str
    architecture: str
    ip: List[str]
    os: Dict[str, str]

class MessageLevel(BaseModel):
    level_name: str
    level: int

class LogFile(BaseModel):
    path: str
    offset: int

class LogSource(BaseModel):
    agent: Agent
    timestamp: datetime = Field(alias="@timestamp")
    message: str
    fields: Dict[str, str]
    version: str = Field(alias="@version")
    host: Host
    msg: MessageLevel
    input: Dict[str, str]
    tags: List[str]
    ecs: Dict[str, str]
    log: Dict[str, Any]
    type: str

class ElkLog(BaseModel):
    index: str = Field(alias="_index")
    id: str = Field(alias="_id")
    score: float = Field(default=0.0, alias="_score")
    ignored: Optional[List[str]] = Field(default=None, alias="_ignored")
    source: dict = Field(alias="_source")
    fields: Optional[dict] = None
    elk_id: Optional[int] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AIAnalysis(BaseModel):
    timestamp: str
    error_type: str
    error_message: str
    root_cause: str
    impact: str
    analysis: str
    severity: str
    immediate_actions: List[str]
    resolution_steps: List[str]
    needs_immediate_attention: bool

class AnalysisBatch(BaseModel):
    id: str = Field(alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    logs: List[dict]  # Original logs
    analyses: List[dict]  # Raw AI analyses
    total_errors: int

    model_config = {
        "populate_by_name": True
    }

class ErrorLog(BaseModel):
    timestamp: datetime
    message: str
    level: str
    host: str
    analysis: Optional[AIAnalysis] = None

class LogDocument(BaseModel):
    id: str = Field(alias="_id")
    source: LogSource
    errors: List[ErrorLog] = []
    last_analyzed: Optional[datetime] = None
    total_errors: int = 0
    critical_errors: int = 0

    model_config = {
        "populate_by_name": True
    }

class BatchAnalysis(BaseModel):
    id: str = Field(alias="_id")
    type: str = "batch_analysis"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str
    logs: List[dict]
    analysis_results: List[dict]
    total_errors: int = 0
    critical_errors: int = 0
    summary: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [{
                "_id": "123",
                "type": "batch_analysis",
                "request_id": "uuid",
                "logs": [{"example": "log data"}],
                "analysis_results": [{"example": "analysis"}]
            }]
        }
    }

class AnalysisResult(BaseModel):
    timestamp: datetime
    log: dict  # Original log
    error_message: str
    analysis: str
    suggestions: List[str]
    severity: str
    resolution_steps: List[str]

class BatchResult(BaseModel):
    id: str = Field(alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    analyses: List[AnalysisResult]
    total_errors: int

    model_config = {
        "populate_by_name": True
    }