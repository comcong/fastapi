import asyncio
import websocket_manager
import json

# 여기를 실제 한투 API WebSocket 수신으로 교체 가능
async def start_kis_receiver():
    print("starting kis receiver 실행됨")
    count = 0
    while True:
        await asyncio.sleep(1)  # 1초마다 수신한다고 가정
        data = f"[한투 실시간 데이터] price: {1000 + count}"
        print("📡 수신됨 →", data)
        data = {"type": "message", "data": data}
        # await websocket_manager.manager.broadcast(data)
        await websocket_manager.manager.broadcast(json.dumps(data)) #, ensure_ascii=False))
        count += 1
