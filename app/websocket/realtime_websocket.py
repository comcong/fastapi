import json
import websockets
from fastapi import WebSocket as fws
from app.kis_invesment.kis_manager import kis_api
import asyncio
import pandas as pd
from app.db import kis_db

connected_clients = set()  # 접속한 클라이언트들의 리스트
task = None                # combined_kis_task() 중복 실행을 방지하기 위한 변수

def jango_list_from_db() -> list[str]:
    data = kis_db.get_data()
    df = pd.DataFrame(data)
    df = df[df['체결수량'].astype(int) > 0]
    # code_list = df['종목코드'].unique().tolist()
    return df

def update_jango_df(df: pd.DataFrame = None) -> pd.DataFrame:
    global jango_df  # 실시간 현재가 데이터 전역변수 사용
    if df is None: df = pd.DataFrame(columns=["종목코드", "새현재가"])
    jango_df = pd.merge(jango_df, df, on='종목코드', how='left')  # 병합
    jango_df['현재가'] = jango_df['현재가'].combine_first(jango_df['새현재가']) # NaN 처리: 새 값이 있으면 반영, 없으면 기존 값 유지
    jango_df = jango_df[['주문번호', '체결시간', '종목코드', '체결수량', '체결단가', '현재가']]
    return jango_df

jango_df = jango_list_from_db()[['주문번호', '체결시간', '종목코드', '체결수량', '체결단가']]
jango_df['현재가'] = ''


pre_code_list = set(jango_df['종목코드'].unique().tolist()) # DB 에서 종목코드 가져옴
# first_subscribe_code = True # 최초 종목코드 등록 여부 정보

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
        task = asyncio.create_task(combined_kis_task()) # combined_kis_task() 실행 정보 담음

    try:
        while True:
            await fws.receive_text()     # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)    # 종료된 클라이언트 제거
        print("클라이언트 제거됨")


async def combined_kis_task():
    jango_df = update_jango_df()
    json_data = jango_df.to_dict(orient="records")  # orient="records"; 딕셔너리 들의 리스트 형태로 변환
    await broadcast(json.dumps({
        "type": "stock_data",
        "data": json_data
    }, ensure_ascii=False))
    # print(json.dumps(json_data, ensure_ascii=False, indent=2))


    # 구독 등록할 tr_id 값 준비
    tr_id_price = 'H0STCNT0'       # 실시간 현재가 tr_id
    tr_id_transaction = 'H0STCNI9' # 실시간 체결알람 모의계좌용 tr_id      실전계좌: 'H0STCNI0'

    kis = kis_api()  # kis 객체 생성



    async with websockets.connect(kis.url) as ws:  # kis 웹소켓 생성; 최초 한개만 생성해야 한다. 여러개 생성되면 치명적 에러 발생
        print("KIS 웹소켓에 연결됨")



        # ============= 구독 요청 하는 부분 =======================
        # ws 객체에 순차적으로 구독 등록; 단 1개의 웹소켓으로 모두 구독 등록한다.; 이것이 핵심!!!
        await kis.subscribe(ws=ws, tr_id=tr_id_transaction)                       # 실시간 체결알람 구독 등록
        await kis.subscribe(ws=ws, tr_id=tr_id_price, code_list=pre_code_list)    # DB에 저장된 종목코드 리스트 현재가 구독 등록



        # =============== 데이터 수신하는 부분 =========================
        # price_df = None
        # trans_df = None
        while True:  # 데이터를 계속 수신한다.

            try:
                raw_data = await ws.recv()                  # ws로부터 데이터 수신
                print("수신된 원본 데이터: ", raw_data)
                data = await kis.make_data(raw_data)         # 데이터 가공
                print("수신된 가공 데이터: ", data)

                if isinstance(data, pd.DataFrame):    # 데이터가 데이터프레임인 경우
                    tr_id = data.iloc[0]['tr_id']
                    if tr_id == 'H0STCNT0':  # 실시간 현재가가 들어오는 경우
                        jango_df = update_jango_df(data[['종목코드', '새현재가']].copy())

                    elif tr_id in ['H0STCNI9', 'H0STCNI0']:  # 체결통보 데이터
                        trans_df = data.copy()
                        print('체결통보 df', trans_df)

                        #  ==== 현재 보유한 종목코드 =====================================================
                        # code_list = trans_df['종목코드'].unique().tolist()  # 이 부분 부터 수정해 보자
                        # ====  이 종목 리스트와 이미 구독된 종목 리스트 비교하여 구독 등록 및 해제 해 보자
                        #  ============================================================================


                    # # if price_df is not None and trans_df is not None:  # price_df 와 trans_df 둘 다 준비된 경우에만 병합 수행
                    # df = jango_df.merge(price_df, on='종목코드', how='left')
                    # print('df: ')
                    # print(df.columns.tolist())
                    #
                    # # tr_id  고객ID      계좌번호    주문번호   원주문번호  ... 신용구분 신용대출일자 체결종목명   주문가격    현재가
                    # df['수익률'] = ''
                    #
                    # print('병합된 df:')
                    # print(df.columns.tolist())
                    # print(df)

                    json_data = jango_df.to_dict(orient="records") # orient="records"; 딕셔너리 들의 리스트 형태로 변환
                    await broadcast(json.dumps({
                        "type": "stock_data",
                        "data": json_data
                    }, ensure_ascii=False))



                    # print(json.dumps(json_data, ensure_ascii=False, indent=2))



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
