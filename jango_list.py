from app.db import kis_db
import pandas as pd
from supabase import create_client, Client
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Qt5Agg")

from app.core.config import settings

url: str = settings.SUPABASE_URL
key: str = settings.SUPABASE_KEY
supabase: Client = create_client(url, key)

def get_data():
    """Supabase에서 데이터 가져오기"""
    try:
        data = supabase.table('acc_jango').select("*").limit(None).execute().data
        print(f"데이터를 성공적으로 가져왔습니다!")
        print(data)
        return data
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return None

# 한글 폰트 설정 (Windows: 맑은 고딕, Mac: AppleGothic, Linux: 나눔고딕 등)
plt.rcParams['font.family'] = 'Malgun Gothic'   # Windows
# plt.rcParams['font.family'] = 'AppleGothic'  # Mac
# plt.rcParams['font.family'] = 'NanumGothic'  # Linux

supa_db = get_data()

jango_df = pd.DataFrame(supa_db).sort_values('시간')
jango_df['시간'] = pd.to_datetime(jango_df['시간'])
jango_df['잔고'] = jango_df['잔고'].astype('int')
print(jango_df)

jango_df.plot(x="시간", y="잔고", kind="line", title="잔고 추이")
plt.show()

print(jango_df)