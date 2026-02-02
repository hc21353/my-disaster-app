import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 설정 및 데이터 로딩
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="The Pulse of Disasters",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 파일 로드 함수
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")

@st.cache_data
def load_data():
    # 데이터 로드 (업로드하신 파일 경로에 맞게 수정 필요)
    df = pd.read_csv("emdat.csv")
    
    # 필요한 전처리
    # 날짜 처리 등 (Start Year가 정수형인지 확인)
    df = df[df['Start Year'].notna()]
    df['Start Year'] = df['Start Year'].astype(int)
    
    # 한국 데이터 별도 추출 (South Korea, Korea, Rep. 등 확인 필요)
    # 데이터 내 Country 명칭 확인 후 필터링. 보통 'Korea (the Republic of)' 등으로 표기됨
    # 여기서는 예시로 'Korea'가 포함된 경우를 찾습니다.
    return df

try:
    df = load_data()
except FileNotFoundError:
    st.error("데이터 파일을 찾을 수 없습니다. 'emdat.csv' 파일을 같은 폴더에 넣어주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 2. 사이드바 (컨트롤 패널)
# -----------------------------------------------------------------------------
st.sidebar.header("🕹️ Filter Options")

# 연도 슬라이더
min_year = int(df['Start Year'].min())
max_year = int(df['Start Year'].max())
selected_year_range = st.sidebar.slider(
    "분석 기간 선택",
    min_year, max_year, (1950, 2024) # 기본값 설정
)

# 데이터 필터링
df_filtered = df[
    (df['Start Year'] >= selected_year_range[0]) &
    (df['Start Year'] <= selected_year_range[1])
]

# 재해 유형 필터
disaster_groups = st.sidebar.multiselect(
    "재해 그룹 선택 (Disaster Group)",
    options=df_filtered['Disaster Group'].unique(),
    default=df_filtered['Disaster Group'].unique()
)
df_final = df_filtered[df_filtered['Disaster Group'].isin(disaster_groups)]

# -----------------------------------------------------------------------------
# 3. 메인 대시보드 구조
# -----------------------------------------------------------------------------

# 헤더 섹션
st.markdown('<p class="main-title">The Pulse of Disasters 🌍</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">글로벌 자연재해 발생 패턴과 인류 대응력의 진화: 디커플링(Decoupling) 분석</p>', unsafe_allow_html=True)

# KPI 섹션
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("총 발생 건수", f"{len(df_final):,} 건")
with col2:
    total_deaths = df_final['Total Deaths'].sum()
    st.metric("총 사망자 수", f"{int(total_deaths):,} 명")
with col3:
    total_affected = df_final['Total Affected'].sum()
    st.metric("총 피해 인구", f"{int(total_affected):,} 명")
with col4:
    # 데이터가 비어있을 수 있으므로 처리
    cost = df_final['Total Damage (\'000 US$)'].sum()
    st.metric("총 피해액 (천 달러)", f"${int(cost):,}")

st.markdown("---")

# -----------------------------------------------------------------------------
# 섹션 1: The Decoupling (핵심 메시지)
# -----------------------------------------------------------------------------
st.subheader("📊 Insight 1: 재해는 늘었지만, 인류는 강해졌다 (Decoupling)")

# 연도별 집계
yearly_stats = df_final.groupby('Start Year').agg({
    'Disaster Type': 'count',
    'Total Deaths': 'sum'
}).reset_index()
yearly_stats.columns = ['Year', 'Occurrence', 'Deaths']

# 이중축 차트 (Bar + Line)
fig_decoupling = go.Figure()

# Bar Chart (발생 건수)
fig_decoupling.add_trace(go.Bar(
    x=yearly_stats['Year'],
    y=yearly_stats['Occurrence'],
    name='발생 건수',
    marker_color='#FF6B6B',
    opacity=0.6,
    yaxis='y1'
))

# Line Chart (사망자 수)
fig_decoupling.add_trace(go.Scatter(
    x=yearly_stats['Year'],
    y=yearly_stats['Deaths'],
    name='사망자 수',
    mode='lines+markers',
    line=dict(color='#4ECDC4', width=3),
    yaxis='y2'
))

# 레이아웃 설정 (이중축)
fig_decoupling.update_layout(
    xaxis=dict(title='Year'),
    yaxis=dict(title='발생 건수 (건)', side='left'),
    yaxis2=dict(title='사망자 수 (명)', side='right', overlaying='y'),
    legend=dict(x=0, y=1.2, orientation='h'),
    template="plotly_dark",
    height=500
)

st.plotly_chart(fig_decoupling, use_container_width=True)

# -----------------------------------------------------------------------------
# 섹션 2: Global Overview (지도 + 재해 유형)
# -----------------------------------------------------------------------------
col_map, col_type = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ Global Heatmap: 어디가 가장 위험한가?")
    # 지도 데이터 집계 (국가별)
    country_stats = df_final.groupby('ISO').agg({
        'Total Affected': 'sum',
        'Country': 'first' # 이름 가져오기
    }).reset_index()
    
    fig_map = px.choropleth(
        country_stats,
        locations="ISO",
        color="Total Affected",
        hover_name="Country",
        color_continuous_scale=px.colors.sequential.Plasma,
        template="plotly_dark",
        projection="natural earth" # 평면 지도 (지구본 원하면 'orthographic')
    )
    fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)

with col_type:
    st.subheader("🌪️ 재해 유형 분석")
    # Sunburst Chart
    fig_sun = px.sunburst(
        df_final,
        path=['Disaster Group', 'Disaster Type'],
        values='Total Affected', # 크기 기준
        color='Disaster Group',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_sun.update_layout(template="plotly_dark")
    st.plotly_chart(fig_sun, use_container_width=True)

# -----------------------------------------------------------------------------
# 섹션 3: Focus on Korea (인명 피해 상세)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🇰🇷 Focus on Korea: 한국의 재해 패턴")

# 한국 데이터 필터링 (ISO 코드가 KOR인 경우)
df_korea = df[df['ISO'] == 'KOR'] # 혹은 'South Korea' 이름 확인 필요

if df_korea.empty:
    st.info("선택된 기간 내 한국 데이터가 없습니다.")
else:
    korea_tab1, korea_tab2 = st.tabs(["연도별 피해 추이", "재해 유형별 인명피해"])
    
    with korea_tab1:
        # 연도별 발생 건수와 피해자 수 시각화
        fig_kor = px.bar(
            df_korea, 
            x='Start Year', 
            y='Total Affected',
            color='Disaster Type',
            title="연도별 한국 재해 피해 인구 (Stacked Bar)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_kor, use_container_width=True)
        
    with korea_tab2:
        # 사람 히스토그램 느낌 (Dot Plot)
        # Scatter Plot을 활용하여 데이터 포인트로 사람을 표현
        st.markdown("#### 재해 유형별 사망/실종 규모 (Bubble Size = 사망자 수)")
        
        fig_bubble = px.scatter(
            df_korea,
            x="Start Year",
            y="Disaster Type",
            size="Total Deaths",
            color="Disaster Type",
            hover_name="Event Name",
            size_max=60,
            template="plotly_dark"
        )
        st.plotly_chart(fig_bubble, use_container_width=True)