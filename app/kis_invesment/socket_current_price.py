import websockets
import asyncio
from app.services.approval_key import get_approval_key
from app.core.config import settings
import json

approval_key = get_approval_key()
tr_id = 'H0STCNT0'
tr_key = '000270'

if settings.KIS_USE_MOCK == True:
    base_url = 'ws://ops.koreainvestment.com:31000' # 모의
elif settings.KIS_USE_MOCK == False:
    base_url = 'ws://ops.koreainvestment.com:21000' # 실전

url = f"{base_url}/tryitout/H0STCNT0"

senddata = {"header" :
                  {
                  "approval_key" : approval_key,
                  "custtype" : "P",
                  "tr_type" : "1",
                  "content-type" : "utf-8"
                  },
                  "body" : {
                    "input":{
                      "tr_id" : tr_id,
                      "tr_key" : tr_key
                      }
                    }
                  }


async def receive_from_kis_invesment():
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(senddata))
        while True:
            data = await ws.recv()
            print(data)


asyncio.run(receive_from_kis_invesment())
