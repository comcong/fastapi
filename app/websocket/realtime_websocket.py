import json
import websockets
from fastapi import WebSocket as fws
from app.kis_invesment.kis_manager import kis_api
import asyncio

connected_clients = set()  # 접속한 클라이언트들의 리스트
task = None                # combined_kis_task() 중복 실행을 방지하기 위한 변수
code_list = ['015760', '052690', '005380', '000270', '027360']

# 실시간 체결알람 엔드포인트
async def endpoint(fws: fws):
    global task                 # 전역변수로 선언해야 값 변경 가능

    await fws.accept()          # 클라이언트에 fws 연결 허용
    connected_clients.add(fws)  # fws에 접속하면 클라이언트 리스트에 추가
    print("새로운 클라이언트 추가")

    # task 값이 None일 때만  combined_kis_task 실행; 이후에는 실행 방지
    if task is None or task.done():
        task = asyncio.create_task(combined_kis_task()) # 비동기 작업(Task) 객체를 담는다.

    try:
        while True:
            await fws.receive_text()     # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)    # 종료된 클라이언트 제거
        print("클라이언트 제거됨")


async def combined_kis_task():
    tr_id_price = 'H0STCNT0'       # 실시간 현재가 tr_id
    tr_id_transaction = 'H0STCNI9' # 실시간 체결알람 모의계좌용 tr_id      실전계좌: 'H0STCNI0'

    kis = kis_api()  # kis 객체 생성

    async with websockets.connect(kis.url) as ws:  # kis 웹소켓 생성; 최초 한개만 생성해야 한다. 여러개 생성되면 치명적 에러 발생
        print("KIS 웹소켓에 연결됨")

        # ws 객체에 순차적으로 구독 요청; 단 1개의 웹소켓으로 여러가지 구독 등록한다.; 이것이 핵심!!!
        await kis.subscribe(ws=ws, tr_id=tr_id_transaction)                   # 실시간 체결알람 구독 등록
        await kis.subscribe(ws=ws, tr_id=tr_id_price, code_list=code_list)    # 실시간 현재가 구독 등록

        while True:
            try:
                raw_data = await ws.recv()                  # ws로부터 데이터 수신
                print("수신된 원본 데이터: ", raw_data)
                # try:
                #     data = json.loads(raw_data)         # 문자열을 딕셔너리로 변환
                #     tr_id = data['header']['tr_id']     # tr_id 값 추출
                # except:                                 # 문자열이 딕셔너리 형태가 아니면 패스
                #     pass
                data = await kis.make_data(raw_data)         # 데이터 가공
                print("수신된 가공 데이터: ", data)

                for client in connected_clients.copy():   # 리스트 값을 변경할 때는 copy해야 에러 방지된다.
                    try:
                        await client.send_text(json.dumps(data, ensure_ascii=False))  # 각 클라이언트들에게 데이터 전송
                    except Exception as e:
                        print("클라이언트 전송 실패:", e)
                        connected_clients.remove(client)   # fws 에 데이터 전송 실패시 리스트 요소 제거; 리스트 요소 변경

            except Exception as e:
                print("웹소켓 수신 오류:", e)
                break
