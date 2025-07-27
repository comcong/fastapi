import json
import websockets
from fastapi import WebSocket as fws
from app.kis_invesment.kis_manager import kis_api
import asyncio
import pandas as pd

connected_clients = set()  # 접속한 클라이언트들의 리스트
task = None                # combined_kis_task() 중복 실행을 방지하기 위한 변수
code_list = ['015760', '052690', '005380', '000270', '027360']

# 모든 클라이언트들 에게 메시지 전송하는 함수
async def broadcast(message: str):
    for client in connected_clients.copy():
        try:
            await client.send_text(message)
        except Exception as e:
            print("클라이언트 전송 실패:", e)
            connected_clients.remove(client)

# 실시간 체결알람 엔드포인트
async def endpoint(fws: fws):
    global task                 # 전역변수로 선언해야 값 변경 가능

    await fws.accept()          # 클라이언트에 fws 연결 허용
    connected_clients.add(fws)  # fws에 접속하면 클라이언트 리스트에 추가
    print("새로운 클라이언트 추가")

    # task 값이 None일 때만  combined_kis_task 실행; 이후에는 실행 방지
    if task is None or task.done():
        task = asyncio.create_task(combined_kis_task())

    try:
        while True:
            await fws.receive_text()     # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)    # 종료된 클라이언트 제거
        print("클라이언트 제거됨")


async def combined_kis_task():

    # 구독 등록할 tr_id 값 준비
    tr_id_price = 'H0STCNT0'       # 실시간 현재가 tr_id
    tr_id_transaction = 'H0STCNI9' # 실시간 체결알람 모의계좌용 tr_id      실전계좌: 'H0STCNI0'

    kis = kis_api()  # kis 객체 생성

    async with websockets.connect(kis.url) as ws:  # kis 웹소켓 생성; 최초 한개만 생성해야 한다. 여러개 생성되면 치명적 에러 발생
        print("KIS 웹소켓에 연결됨")

        # ============= 구독 요청 하는 부분 =======================
        # ws 객체에 순차적으로 구독 등록; 단 1개의 웹소켓으로 모두 구독 등록한다.; 이것이 핵심!!!
        await kis.subscribe(ws=ws, tr_id=tr_id_transaction)                   # 실시간 체결알람 구독 등록
        await kis.subscribe(ws=ws, tr_id=tr_id_price, code_list=code_list)    # 실시간 현재가 구독 등록



        # =============== 데이터 수신하는 부분 =========================
        price_df = None
        trans_df = None

        while True:  # 데이터를 계속 수신한다.
            try:
                raw_data = await ws.recv()                  # ws로부터 데이터 수신
                print("수신된 원본 데이터: ", raw_data)
                data = await kis.make_data(raw_data)         # 데이터 가공
                print("수신된 가공 데이터: ", data)

                if isinstance(data, pd.DataFrame):    # 데이터가 데이터프레임인 경우
                    tr_id = data.iloc[0]['tr_id']
                    if tr_id == 'H0STCNT0':
                        price_df = data.copy()
                    elif tr_id in ['H0STCNI9', 'H0STCNI0']:
                        trans_df = data.copy()

                    if price_df is not None and trans_df is not None:  # price_df 와 trans_df 둘 다 준비된 경우에만 병합 수행
                        df = trans_df.merge(
                            price_df[['종목코드', '현재가']], on='종목코드', how='left'
                        )
                        json_data = df.to_dict(orient="records") # orient="records"; 딕셔너리 들의 리스트 형태로 변환
                        await broadcast(json.dumps({
                            "type": "stock_data",
                            "data": json_data
                        }, ensure_ascii=False))



                else:                               # 데이터가 일반 딕셔너리 타입인 경우
                    await broadcast(json.dumps({
                        "type": "message",
                        "data": data
                    }, ensure_ascii=False))

            except Exception as e:
                print("웹소켓 수신 오류:", e)
                # break
                await asyncio.sleep(5)
                continue  # 통신 끊겼을 때 재 연결
