import asyncio
from app.database import SessionLocal
from app.sync.erpnext import ERPNextSync

async def sync():
    db = SessionLocal()
    try:
        sync_client = ERPNextSync(db)
        print("Starting ERPNext full sync...")
        await sync_client.sync_all(full_sync=True)
        print("ERPNext sync completed")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

asyncio.run(sync())
