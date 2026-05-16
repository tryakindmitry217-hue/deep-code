import statistics
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from .celery_app import celery_app
from .database import async_session
from .models import Device, DataRecord

async def _calculate_stats(device_id, start_time, end_time):
    async with async_session() as session:
        q = select(DataRecord).where(DataRecord.device_id == device_id)
        if start_time:
            q = q.where(DataRecord.timestamp >= start_time)
        if end_time:
            q = q.where(DataRecord.timestamp <= end_time)
        result = await session.execute(q)
        records = result.scalars().all()

        stats = {}
        for axis in ['x', 'y', 'z']:
            values = [getattr(r, axis) for r in records]
            if not values:
                stats[axis] = {"min": None, "max": None, "count": 0, "sum": 0.0, "median": None}
            else:
                stats[axis] = {
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                    "sum": sum(values),
                    "median": statistics.median(values),
                }
        return stats

@celery_app.task(bind=True)
def analyze_device(self, device_identifier, start_time=None, end_time=None):
    import asyncio
    loop = asyncio.get_event_loop()
    stats = loop.run_until_complete(_calculate_stats_by_identifier(device_identifier, start_time, end_time))
    return {"device_identifier": device_identifier, "parameters": stats}

async def _calculate_stats_by_identifier(device_identifier, start_time, end_time):
    async with async_session() as session:
        q = select(Device).where(Device.device_identifier == device_identifier)
        res = await session.execute(q)
        device = res.scalar_one_or_none()
        if not device:
            return {"error": "Device not found"}
        return await _calculate_stats(device.id, start_time, end_time)

@celery_app.task(bind=True)
def analyze_user(self, user_id, start_time=None, end_time=None):
    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_analyze_user_async(user_id, start_time, end_time))
    return result

async def _analyze_user_async(user_id, start_time, end_time):
    async with async_session() as session:
        q = select(Device).where(Device.user_id == user_id)
        res = await session.execute(q)
        devices = res.scalars().all()
        if not devices:
            return {"user_id": user_id, "aggregated": {}, "per_device": []}

        all_stats = {"x": [], "y": [], "z": []}
        per_device_list = []
        for device in devices:
            stats = await _calculate_stats(device.id, start_time, end_time)
            per_device_list.append({
                "device_identifier": device.device_identifier,
                "parameters": stats
            })
            for axis in ['x', 'y', 'z']:
                if stats[axis]['count'] > 0:
                    all_stats[axis].extend(
                        [getattr(r, axis) for r in await _get_records(device.id, start_time, end_time)]
                    )

        aggregated = {}
        for axis in ['x', 'y', 'z']:
            vals = all_stats[axis]
            if not vals:
                aggregated[axis] = {"min": None, "max": None, "count": 0, "sum": 0.0, "median": None}
            else:
                aggregated[axis] = {
                    "min": min(vals),
                    "max": max(vals),
                    "count": len(vals),
                    "sum": sum(vals),
                    "median": statistics.median(vals),
                }
        return {"user_id": user_id, "aggregated": aggregated, "per_device": per_device_list}

async def _get_records(device_id, start_time, end_time):
    async with async_session() as session:
        q = select(DataRecord).where(DataRecord.device_id == device_id)
        if start_time:
            q = q.where(DataRecord.timestamp >= start_time)
        if end_time:
            q = q.where(DataRecord.timestamp <= end_time)
        res = await session.execute(q)
        return res.scalars().all()
