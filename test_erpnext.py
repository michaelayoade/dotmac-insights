import asyncio
from app.database import SessionLocal
from app.sync.erpnext import ERPNextSync

async def test():
    db = SessionLocal()
    try:
        sync = ERPNextSync(db)
        result = await sync.test_connection()
        status = "OK" if result else "FAILED"
        print(f"ERPNext connection: {status}")
        return result
    finally:
        db.close()

asyncio.run(test())
