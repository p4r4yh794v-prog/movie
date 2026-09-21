
import streamlit as st
import requests
from datetime import datetime, timedelta, timezone


# ==================================================
# 1. 기본 설정
# ==================================================

# 한국 시간(KST)은 UTC보다 9시간 빠르다.
# 배포 서버가 한국 시간이 아니어도 정확한 날짜를 계산하기 위해 사용한다.
KST = timezone(timedelta(hours=9))

# KOBIS 일일 박스오피스 API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# Streamlit 페이지 설정
st.set_page_config(
    page_title="박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 일일 박스오피스")
st.caption("KOBIS 공식 API를 이용한 일일 박스오피스 조회")


# ==================================================
# 2. 한국 시간 기준 날짜 계산
# ==================================================

# 현재 한국 날짜를 구한다.
today_kst = datetime.now(KST).date()

# 오늘은 아직 집계 전이므로 가장 늦게 선택할 수 있는 날짜는 어제다.
yesterday_kst = today_kst - timedelta(days=1)


# ==================================================
# 3. 날짜 선택
# ==================================================

st.subheader("📅 조회할 날짜를 선택하세요")

selected_date = st.date_input(
    "조회 날짜",
    value=yesterday_kst,
    min_value=datetime(2004, 1, 1).date(),
    max_value=yesterday_kst,
)

# 날짜를 KOBIS가 요구하는 YYYYMMDD 형식으로 바꾼다.
target_date = selected_date.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = selected_date.strftime("%Y-%m-%d")


# ==================================================
# 4. KOBIS API 호출
# ==================================================

# 같은 날짜를 다시 조회하면 1시간 동안 저장해 둔 결과를 사용한다.
# 따라서 같은 날짜를 여러 번 선택해도 API를 계속 호출하지 않는다.
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Streamlit Secrets에서 KOBIS 인증키를 가져온다.
    # 실제 인증키는 코드에 직접 작성하지 않는다.
    try:
        kobis_key = st.secrets["KOBIS_KEY"]

    except KeyError:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Secrets에 "
                "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
            ),
        }

    # KOBIS API에 전달할 요청값
    params = {
        "key": kobis_key,
        "targetDt": target_dt,
    }

    try:
        # API에 요청한다.
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킨다.
        response.raise_for_status()

        # JSON 데이터를 가져온다.
        data = response.json()

    except requests.exceptions.RequestException:
        return {
            "success": False,
            "message": (
                "KOBIS API에 요청하는 중 문제가 발생했습니다.\n\n"
                "인터넷 연결이나 KOBIS 서버 상태를 확인한 뒤 "
                "다시 시도해 주세요."
            ),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API가 올바른 데이터를 보내지 않았습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            ),
        }

    # ==================================================
    # 5. faultInfo 확인
    # ==================================================

    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있다.
    # 따라서 faultInfo가 있는지 따로 확인해야 한다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_message = fault_info.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다.",
        )

        return {
            "success": False,
            "message": (
                "KOBIS API 오류가 발생했습니다.\n\n"
                f"오류 내용: {fault_message}\n\n"
                "KOBIS_KEY가 올바른지 확인해 주세요."
            ),
        }

    # ==================================================
    # 6. 박스오피스 결과 확인
    # ==================================================

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답을 확인하거나 "
                "잠시 후 다시 시도해 주세요."
            ),
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        [],
    )

    # 영화 목록이 비어 있다면
    # 사용자가 요청한 문구를 정확하게 안내한다.
    if not movie_list:
        return {
            "success": False,
            "message": "그날은 아직 집계 전입니다.",
            "empty": True,
        }

    return {
        "success": True,
        "movies": movie_list,
    }


# ==================================================
# 7. 선택한 날짜의 데이터 가져오기
# ==================================================

result = get_boxoffice(target_date)


# 오류가 발생했을 때
if not result["success"]:
    if result.get("empty"):
        st.info(f"📌 {display_date}은(는) 아직 집계 전입니다.")
    else:
        st.error(result["message"])

    st.stop()


movies = result["movies"]


# ==================================================
# 8. 숫자 데이터 숫자형으로 변환
# ==================================================

# KOBIS API에서는 숫자도 문자열로 전달된다.
# 정렬과 그래프에 제대로 사용하기 위해 숫자로 변환한다.
for movie in movies:

    movie["rank"] = int(movie.get("rank", 0))

    movie["rankInten"] = int(
        movie.get("rankInten", 0)
    )

    movie["audiCnt"] = int(
        movie.get("audiCnt", 0)
    )

    movie["audiAcc"] = int(
        movie.get("audiAcc", 0)
    )

    movie["scrnCnt"] = int(
        movie.get("scrnCnt", 0)
    )


# ==================================================
# 9. 순위순으로 정렬
# ==================================================

movies_sorted = sorted(
    movies,
    key=lambda x: x["rank"],
)


# ==================================================
# 10. 선택한 날짜 표시
# ==================================================

st.subheader(f"📅 {display_date} 박스오피스")


# ==================================================
# 11. 1위 영화
# ==================================================

first_movie = movies_sorted[0]

# 누적관객이 100만 명 이상이면 트로피를 붙인다.
first_movie_name = first_movie["movieNm"]

if first_movie["audiAcc"] > 1_000_000:
    first_movie_name += " 🏆"

st.markdown(
    f"## 🥇 1위: {first_movie_name}"
)


# ==================================================
# 12. 1위 영화 지표 카드
# ==================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        "누적관객",
        f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개",
    )


# ==================================================
# 13. 전체 순위 표 만들기
# ==================================================

st.subheader("📋 전체 순위")

table_data = []

for movie in movies_sorted:

    # 영화명 만들기
    movie_name = movie["movieNm"]

    # 누적관객이 100만 명을 넘은 영화에는 트로피 추가
    if movie["audiAcc"] > 1_000_000:
        movie_name += " 🏆"

    # 전날 대비 순위 변동 표시
    rank_inten = movie["rankInten"]

    if rank_inten > 0:
        # 양수 = 순위가 올라감
        rank_change = f"🔴 ↑ {rank_inten}"

    elif rank_inten < 0:
        # 음수 = 순위가 내려감
        rank_change = f"🔵 ↓ {abs(rank_inten)}"

    else:
        # 0 = 순위 변동 없음
        rank_change = "－"

    table_data.append(
        {
            "순위": movie["rank"],
            "증감": rank_change,
            "영화명": movie_name,
            "개봉일": movie.get("openDt", ""),
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )


# ==================================================
# 14. 표 출력
# ==================================================

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,

    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),

        "증감": st.column_config.TextColumn(
            "전일 대비",
        ),

        "영화명": st.column_config.TextColumn(
            "영화명",
        ),

        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),

        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d",
        ),

        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d",
        ),

        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d",
        ),
    },
)


# ==================================================
# 15. 관객수 상위 5편
# ==================================================

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서대로 정렬한다.
top5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True,
)[:5]


# 그래프에 사용할 데이터를 만든다.
# 영화명을 키로, 관객수를 값으로 사용한다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}


# 막대그래프 출력
st.bar_chart(
    chart_data,
    horizontal=True,
)


# ==================================================
# 16. 데이터 출처
# ==================================================

st.caption(
    f"※ {display_date} 기준 · 데이터 출처: KOBIS 일일 박스오피스 API"
)
