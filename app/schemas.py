from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StatsInput(BaseModel):
    x: float
    y: float
    z: float

class UserCreate(BaseModel):
    username: str

class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime
    class Config: orm_mode = True

class DeviceAssign(BaseModel):
    user_id: int

class AnalysisStats(BaseModel):
    min: float
    max: float
    count: int
    sum: float
    median: float

class DeviceAnalysisResult(BaseModel):
    device_identifier: str
    parameters: dict   # {"x": AnalysisStats, "y": AnalysisStats, "z": AnalysisStats}

class UserAnalysisResult(BaseModel):
    user_id: int
    aggregated: dict   # {"x": AnalysisStats, ...}
    per_device: List[DeviceAnalysisResult]

class TaskResponse(BaseModel):
    task_id: str
    status: str

class TaskResult(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
