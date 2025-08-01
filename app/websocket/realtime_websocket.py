import json
import websockets
from fastapi import WebSocket as fws
from app.kis_invesment.kis_manager import kis_api
import asyncio
import pandas as pd
from app.db import kis_db
from app.core.config import settings

connected_clients = set()  # 접속한 클라이언트들의 리스트
task = None                # combined_kis_task() 중복 실행을 방지하기 위한 변수


def strip_zeros(json_list: list[dict]) -> list[dict]:
    keys_to_strip_zeros = ['주문번호', '체결수량', '체결단가']
    for record in json_list:
        for key in keys_to_strip_zeros:
            if key in record and record[key]:
                try:
                    record[key] = str(int(record[key]))
                except (ValueError, TypeError):
                    pass  # 숫자 변환 불가능한 값은 건너뜀
    return json_list

def jango_db():
    supa_db = kis_db.get_data()
    db_df = pd.DataFrame(supa_db)
    if db_df.empty:
        jango_df = pd.DataFrame(columns=['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가'])
        return jango_df

    else:
        jango_df = db_df[['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가']].sort_values('주문번호')
        return jango_df

def update_jango_df(df: pd.DataFrame = None) -> pd.DataFrame:
    # print('update_jango_df() 실행')
    # print('update_jango_df() df')
    # print(df)
    global jango_df  # 실시간 현재가 데이터 전역변수 사용
    if df is None:
        return jango_df
    else:
        print('타입비교')
        print('현재가', jango_df["현재가"])
        print('새현재가', df["새현재가"])
        jango_df = pd.merge(jango_df, df, on='종목코드', how='left')  # 병합
        print('타입비교')
        print('현재가', jango_df["현재가"])
        print('새현재가', jango_df["새현재가"])
        jango_df.loc[jango_df["새현재가"].notna(), "현재가"] = jango_df["새현재가"]
        jango_df = jango_df.drop(columns=['새현재가'])
        jango_df = jango_df[['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가']]
        # print('update_jango_df() jango_df')
        # print(jango_df)
        return jango_df


jango_df = jango_db()
code_list = []
if not jango_df.empty:
    code_list = jango_df['종목코드'].unique().tolist() # DB 에서 종목코드 가져옴


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
        print('combined_kis_task 호출')

    try:
        while True:
            await fws.receive_text()     # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)    # 종료된 클라이언트 제거
        print("클라이언트 제거됨")


async def combined_kis_task():
    print('combined_kis_task 실행')
    global jango_df

    # print('update_jango_df() 실행 후')
    if not jango_df.empty:
        json_data = jango_df.to_dict(orient="records")  # orient="records"; 딕셔너리 들의 리스트 형태로 변환
        json_data = strip_zeros(json_data)
        await broadcast(json.dumps({
            "type": "stock_data",
            "data": json_data
        }, ensure_ascii=False))
        # print(json.dumps(json_data, ensure_ascii=False, indent=2))


    # 구독 등록할 tr_id 값 준비
    tr_id_price = 'H0STCNT0'       # 실시간 현재가 tr_id
    tr_id_transaction = settings.tr_id_transaction
    kis = kis_api()  # kis 객체 생성


    async with websockets.connect(kis.url) as ws:  # kis 웹소켓 생성; 최초 한개만 생성해야 한다. 여러개 생성되면 치명적 에러 발생
        print("KIS 웹소켓에 연결됨")

        # ============= 구독 요청 하는 부분 =======================
        # ws 객체에 순차적으로 구독 등록; 단 1개의 웹소켓으로 모두 구독 등록한다.; 이것이 핵심!!!
        await kis.subscribe(ws=ws, tr_id=tr_id_transaction)                   # 실시간 체결알람 구독 등록
        if code_list:
            await kis.subscribe(ws=ws, tr_id=tr_id_price, code_list=code_list)    # DB에 저장된 종목코드 리스트 현재가 구독 등록



        # =============== 데이터 수신하는 부분 =========================
        # price_df = None
        # trans_df = None
        while True:  # 데이터를 계속 수신한다.

            try:
                raw_data = await ws.recv()                  # ws로부터 데이터 수신
                print("수신된 원본 데이터: ")
                print(raw_data)
                data = await kis.make_data(raw_data)         # 데이터 가공
                print("수신된 가공 데이터: ")
                print(data)

                if isinstance(data, pd.DataFrame):    # 데이터가 데이터프레임인 경우
                    tr_id = data.iloc[0]['tr_id']
                    if tr_id == 'H0STCNT0':  # 실시간 현재가가 들어오는 경우
                        print('tr_id == "H0STCNT0":')
                        jango_df = update_jango_df(data[['종목코드', '새현재가']].copy())



                    # ===============  체결통보 수신시 ========================
                    elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                        trans_df = data.copy()
                        print('체결통보 df')
                        print('trans_df.columns', trans_df.columns.tolist())
                        print('trans_df.values', trans_df.values.tolist())
                        if trans_df['매도매수구분'].values[0] == '02':    # 01: 매도, 02: 매수
                            jango_df = await kis.buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df, code_list=code_list)


                        elif trans_df['매도매수구분'].values[0] == '01':    # 01: 매도, 02: 매수
                            jango_df = kis.sell_update(jango_df=jango_df, trans_df=trans_df)

                        print('jango_df')
                        print(jango_df)


                    json_data = jango_df.to_dict(orient="records") # orient="records"; 딕셔너리 들의 리스트 형태로 변환
                    # json_data = strip_zeros(json_data)
                    await broadcast(json.dumps({
                        "type": "stock_data",
                        "data": json_data
                    }, ensure_ascii=False))  #, default=str))

                    print(json.dumps(json_data, ensure_ascii=False, default=str))



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
