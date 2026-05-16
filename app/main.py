from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional

from . import models, schemas
from .database import get_db, engine, Base
from .celery_app import celery_app
from .tasks import analyze_device, analyze_user

app = FastAPI(title="Stats Service")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post("/data/{device_identifier}", status_code=201)
async def ingest_data(device_identifier: str, data: schemas.StatsInput, db: AsyncSession = Depends(get_db)):
    # Найти или создать устройство
    result = await db.execute(select(models.Device).where(models.Device.device_identifier == device_identifier))
    device = result.scalar_one_or_none()
    if not device:
        device = models.Device(device_identifier=device_identifier)
        db.add(device)
        await db.commit()
        await db.refresh(device)

    record = models.DataRecord(
        device_id=device.id,
        x=data.x, y=data.y, z=data.z
    )
    db.add(record)
    await db.commit()
    return {"message": "Data saved"}

@app.post("/users", response_model=schemas.UserOut)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = models.User(username=user.username)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.get("/users", response_model=list[schemas.UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User))
    return result.scalars().all()

@app.put("/devices/{device_identifier}/assign-user")
async def assign_user(device_identifier: str, body: schemas.DeviceAssign, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Device).where(models.Device.device_identifier == device_identifier))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.user_id = body.user_id
    await db.commit()
    return {"message": "User assigned"}

@app.post("/analysis/device/{device_identifier}", response_model=schemas.TaskResponse)
async def request_device_analysis(
    device_identifier: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None)
):
    task = analyze_device.delay(device_identifier, start_time, end_time)
    return {"task_id": task.id, "status": "PENDING"}

@app.post("/analysis/user/{user_id}", response_model=schemas.TaskResponse)
async def request_user_analysis(
    user_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None)
):
    task = analyze_user.delay(user_id, start_time, end_time)
    return {"task_id": task.id, "status": "PENDING"}

@app.get("/analysis/result/{task_id}", response_model=schemas.TaskResult)
async def get_analysis_result(task_id: str):
    task_result = celery_app.AsyncResult(task_id)
    response = {"task_id": task_id, "status": task_result.status}
    if task_result.ready():
        response["result"] = task_result.result
    return response
