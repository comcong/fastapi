import json
import pandas as pd

price_df = None
trans_df = None

async def kis_data_handler(ws):
    global price_df, trans_df

    while True:
        try:
            raw_data = await ws.recv()
            print("수신된 원본 데이터:", raw_data)

            data = await kis.make_data(raw_data)
            print("수신된 가공 데이터:", data)

            if not isinstance(data, pd.DataFrame):
                # DataFrame 아닌 경우 그대로 JSON으로 모든 클라이언트에게 전송
                await broadcast(json.dumps(data, ensure_ascii=False))
                continue

            # tr_id 추출
            tr_id = data.iloc[0].get("tr_id")

            if tr_id == 'H0STCNT0':
                price_df = data.copy()
            elif tr_id in ['H0STCNI0', 'H0STCNI9']:
                trans_df = data.copy()

            # 병합 가능한 경우
            if price_df is not None and trans_df is not None:
                df = trans_df.merge(
                    price_df[['종목코드', '현재가']],
                    on='종목코드',
                    how='left'
                )

                json_data = df.to_dict(orient="records")
                await broadcast(json.dumps(json_data, ensure_ascii=False))

        except Exception as e:
            print("웹소켓 수신 오류:", e)
            break


# 🔄 모든 클라이언트에게 메시지 전송하는 함수
async def broadcast(message: str):
    for client in connected_clients.copy():  # 복사본 순회
        try:
            await client.send_text(message)
        except Exception as e:
            print("클라이언트 전송 실패:", e)
            connected_clients.remove(client)



await broadcast(json.dumps({"type": "stock_data", "data": json_data}, ensure_ascii=False))




await broadcast(json.dumps(json_data, ensure_ascii=False))