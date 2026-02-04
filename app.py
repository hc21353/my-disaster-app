import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# -----------------------------------------------------------------------------
# 1. 설정 및 데이터 로딩
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="The Pulse of Disasters",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed" # 사이드바 숨김 (지구본 집중)
)

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")

@st.cache_data
def load_data():
    # 메인 데이터 로드
    df = pd.read_csv("data/public_emdat_1970_2020.csv") # Raw Data for Globe Calculation
    df_korea = pd.read_csv("data/korea_deaths_by_disaster_year.csv")
    
    # 전처리: 연도 변환 및 결측치 처리
    df = df[df['Start Year'].notna()]
    df['Start Year'] = df['Start Year'].astype(int)
    
    # 수치 컬럼 결측치 0 처리
    cols_to_fix = ['Total Deaths', 'Total Affected', 'Total Damage (\'000 US$)']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    # 한국 데이터 전처리
    df_korea['Total_Deaths'] = df_korea['Total_Deaths'].fillna(0)
    
    return df, df_korea

try:
    df_raw, df_korea_raw = load_data()
except FileNotFoundError:
    st.error("데이터 파일을 찾을 수 없습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 2. 메인 헤더
# -----------------------------------------------------------------------------
st.markdown('<p class="main-title">The Pulse of Disasters 🌍</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Decoupling: Disaster Frequency vs. Human Impact</p>', unsafe_allow_html=True)
st.markdown("---")

# -----------------------------------------------------------------------------
# 3. GLOBAL SECTION: The Globe
# -----------------------------------------------------------------------------

# (1) 데이터 준비: 연도별/지역별/재해유형별 집계
# Top 7 재해 유형 선정 (전체 기간 기준 빈도수)
# Top 5 재해 유형 선정 (전체 기간 기준 빈도수)
top_5_disasters = df_raw["Disaster Type"].value_counts().nlargest(5).index.tolist()

# 사용자 선택(토글): 기본은 Top 5 전체 선택
selected_types = st.multiselect(
    "Select Disaster Types (Top 5)",
    options=top_5_disasters,
    default=top_5_disasters
)

# 선택이 비면 전체로 fallback (안 보이는 화면 방지)
if len(selected_types) == 0:
    selected_types = top_5_disasters

df_globe = df_raw[df_raw["Disaster Type"].isin(selected_types)].copy()


# 컨트롤 패널 (토글 및 슬라이더)
c1, c2, c3 = st.columns([0.1, 6, 1.9]) #[1, 6, 1] 가운데
# Metric 선택 토글
metric_choice = st.radio(
    "Select Visual Metric:",
    ('Total Occurrences', 'Total Deaths', 'Total Affected'),
    horizontal=True,
    index=0
)
with c2:    
    # 색상 및 데이터 컬럼 매핑
    if metric_choice == 'Total Occurrences':
        color_scale = 'Oranges'
        value_col = 'Event Name' # Count용
        agg_func = 'count'
    elif metric_choice == 'Total Deaths':
        color_scale = 'Reds'
        value_col = 'Total Deaths'
        agg_func = 'sum'
    else: # Affected
        color_scale = 'YlOrBr' # Yellow base
        value_col = 'Total Affected'
        agg_func = 'sum'

    # 연도 슬라이더
    min_year, max_year = int(df_globe['Start Year'].min()), int(df_globe['Start Year'].max())
    
selected_year = st.slider("Select Year", min_year, max_year-1, 2023)

# (2) 선택된 연도 데이터 필터링 및 집계
df_year = df_globe[df_globe['Start Year'] == selected_year]

# 지역(Region)별 집계
region_stats = df_year.groupby(['Region']).agg({
    value_col: agg_func
}).rename(columns={value_col: 'Value'}).reset_index()

# 지도 시각화를 위해 ISO 코드 매핑 (Region -> 각 Region에 속한 모든 국가의 ISO)
# Plotly Choropleth는 ISO 코드를 기반으로 색칠하므로, Region 값을 해당 Region의 모든 국가에 할당합니다.
df_iso_mapping = df_raw[['Region', 'ISO', 'Country']].drop_duplicates()
map_data = pd.merge(df_iso_mapping, region_stats, on='Region', how='left').fillna(0)

# (3) 지구본 시각화
fig_globe = px.choropleth(
    map_data,
    locations="ISO",
    color="Value",
    hover_name="Region", # 호버 시 대륙/지역 이름 표시
    hover_data={"ISO": False, "Country": True, "Value": True},
    color_continuous_scale=color_scale,
    projection="orthographic", # 지구본 모드
    template="plotly_dark",
    title=f"Global {metric_choice} in {selected_year}"
)

fig_globe.update_layout(
    height=700,
    margin={"r":0,"t":50,"l":0,"b":0},
    geo=dict(
        showframe=False,
        showcoastlines=False,
        projection_type='orthographic',
        bgcolor='rgba(0,0,0,0)',
        lakecolor='rgba(0,0,0,0)',
        oceancolor='rgba(20,20,30,1)'
    ),
    coloraxis_colorbar=dict(
        title=dict(text=metric_choice, side="right"),
        x=0.9,
    )
)

st.plotly_chart(fig_globe, use_container_width=True)
# -----------------------------------------------------------------------------
# 3_2. Area plot (Global Trend by Disaster Type)
# -----------------------------------------------------------------------------
import plotly.express as px

st.markdown("---")
st.subheader("🌐 Disaster Occurrences by Type Over Time")

# -----------------------------
# 0) 상위 토글: Region 선택 (Global 포함)
# -----------------------------
regions = ["Global"] + sorted(df_raw["Region"].dropna().unique().tolist())
selected_region = st.radio("Select Region", regions, horizontal=True, index=0)

# Region 필터링
if selected_region == "Global":
    df_region = df_raw.copy()
else:
    df_region = df_raw[df_raw["Region"] == selected_region].copy()

# -----------------------------
# 1) 선택된 Region 기준 Top 5 Disaster Type
# -----------------------------
TOP_N = 5
top_types = (
    df_region["Disaster Type"]
    .value_counts()
    .nlargest(TOP_N)
    .index
    .tolist()
)

# Region에 데이터가 너무 없어서 top_types가 비는 경우 방어
if len(top_types) == 0:
    st.warning("해당 Region에는 표시할 데이터가 없습니다.")
    st.stop()

# -----------------------------
# 2) 하위 토글: Top 5 가로 체크박스
#    (색상/순서 고정 위해 top_types 순서 유지)
# -----------------------------
st.caption("Select Disaster Types (Top 5 in selected region)")

palette = px.colors.qualitative.Plotly
color_map = {t: palette[i % len(palette)] for i, t in enumerate(top_types)}

cols = st.columns(len(top_types))
selected_types = []

for col, t in zip(cols, top_types):
    with col:
        if st.checkbox(t, value=True, key=f"chk_{selected_region}_{t}"):
            selected_types.append(t)

# 아무것도 선택 안 하면: 그래프 대신 안내
if len(selected_types) == 0:
    st.info("👆 최소 1개 이상의 재해 유형을 선택해야 그래프가 표시됩니다.")
    st.stop()

# -----------------------------
# 3) 집계: (연도 x 유형) 발생 횟수
# -----------------------------
df_occ = (
    df_region[df_region["Disaster Type"].isin(selected_types)]
    .groupby(["Start Year", "Disaster Type"])
    .size()
    .reset_index(name="Occurrences")
)

# 그래프 순서 고정(체크박스 순서 = top_types 순서)
ordered_selected = [t for t in top_types if t in selected_types]
df_occ["Disaster Type"] = pd.Categorical(
    df_occ["Disaster Type"],
    categories=ordered_selected,
    ordered=True
)
df_occ = df_occ.sort_values(["Start Year", "Disaster Type"])

# -----------------------------
# 4) 연도 범위 슬라이더
# -----------------------------
min_y = int(df_occ["Start Year"].min())
max_y = int(df_occ["Start Year"].max())
year_range = st.slider("Year Range", min_y, max_y, (min_y, max_y))

df_occ = df_occ[(df_occ["Start Year"] >= year_range[0]) & (df_occ["Start Year"] <= year_range[1])]

# -----------------------------
# 5) Plotly Area plot (순서 + 색 고정)
# -----------------------------
fig_area = px.area(
    df_occ,
    x="Start Year",
    y="Occurrences",
    color="Disaster Type",
    template="plotly_dark",
    category_orders={"Disaster Type": ordered_selected},  # 순서 고정
    color_discrete_map=color_map,                         # 색 고정
    labels={"Start Year": "Year", "Occurrences": "Occurrences", "Disaster Type": "Type"},
    title=f"{selected_region} — Disaster Occurrences Over Time"
)

# legend가 그래프 가리지 않게 위로 빼기
fig_area.update_layout(
    height=520,
    title=dict(
        x=0.5,
        xanchor="center",
        pad=dict(b=25)
    ),
    legend=dict(
        orientation="h",
        y=1.18,
        x=0.5,
        xanchor="center",
        traceorder="normal"
    ),
    margin=dict(l=20, r=20, t=150, b=20)
)

st.plotly_chart(fig_area, use_container_width=True)



# -----------------------------------------------------------------------------
# 4. KOREA SECTION
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown('<p class="main-title" style="font-size: 2.5rem !important;">🇰🇷 Focus on Korea</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">한국의 재해 사망자 추이 및 규모 시각화</p>', unsafe_allow_html=True)

# 데이터 준비: 한국 데이터
# Top 5 재해 유형 선정
top_5_kor = df_korea_raw.groupby('Disaster Type')['Total_Deaths'].sum().nlargest(5).index.tolist()
df_kor_filtered = df_korea_raw[df_korea_raw['Disaster Type'].isin(top_5_kor)]

# [Chart 1] 연도별 피해 추이 (Stacked Bar)
st.subheader("📊 Annual Death Toll Trend")
fig_bar = px.bar(
    df_kor_filtered,
    x='Year',
    y='Total_Deaths',
    color='Disaster Type',
    template='plotly_dark',
    color_discrete_sequence=px.colors.qualitative.Pastel
)
fig_bar.update_layout(
    xaxis_title=None,
    yaxis_title="Total Deaths",
    legend=dict(orientation="h", y=1.1, x=0.5, xanchor='center'),
    height=400,
    bargap=0.2
)
st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# [Chart 2] Pictogram Visualization
st.subheader("🧍 Impact Visualizer (Pictogram)")

# 컨트롤러 (연도, 재해유형)
col_ctrl1, col_ctrl2 = st.columns([2.2, 1])

with col_ctrl1:
    kor_year = st.slider("Select Year for Pictogram",
                         int(df_kor_filtered['Year'].min()),
                         int(df_kor_filtered['Year'].max()),
                         2003)

with col_ctrl2:
    kor_type = st.selectbox("Select Disaster Type", top_5_kor)




# 선택된 데이터 값 가져오기
subset = df_kor_filtered[
    (df_kor_filtered['Year'] == kor_year) & 
    (df_kor_filtered['Disaster Type'] == kor_type)
]
death_count = subset['Total_Deaths'].sum() if not subset.empty else 0

# 픽토그램 로직
# 1 아이콘 = 10명 (예시)
UNIT_PER_ICON = 1
total_icons = 100 # 그리드 전체 크기 (10x10)
active_icons = math.ceil(death_count / UNIT_PER_ICON)

# 상태 관리를 위한 세션 스테이트 (클릭 여부 확인)
if 'pictogram_active' not in st.session_state:
    st.session_state.pictogram_active = False

# 레이아웃: 왼쪽(버튼/트리거) | 오른쪽(그리드)
col_pic_left, col_pic_right = st.columns([1, 3])

with col_pic_left:
    st.markdown(f"<div style='text-align: center; margin-top: 50px;'>", unsafe_allow_html=True)
    st.markdown(f"<h2>{int(death_count):,} Deaths</h2>", unsafe_allow_html=True)
    
    # 투명 버튼으로 클릭 감지 흉내 (Streamlit 버튼 활용)
    if st.button("🔴 Click to Visualize"):
        st.session_state.pictogram_active = not st.session_state.pictogram_active
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.info(f"1 Block = {UNIT_PER_ICON} Person")

with col_pic_right:
    # HTML 생성
    icon_html = ""
    
    # 색상 결정
    if death_count == 0:
        active_class = ""
    elif death_count > 100:
        active_class = "active-red"
    elif death_count > 50:
        active_class = "active-orange"
    else:
        active_class = "active-yellow"
        
    # 클릭 상태에 따라 활성화 개수 조절
    display_active = active_icons if st.session_state.pictogram_active else 0
    
    # 최대 500개까지만 렌더링 (성능 보호)
    limit_icons = min(active_icons + 50, 200) 
    
    for i in range(limit_icons):
        state_class = active_class if i < display_active else ""
        icon_html += f'<div class="person-icon {state_class}"></div>'
        
    st.markdown(f"""
        <div class="person-grid">
            {icon_html}
        </div>
    """, unsafe_allow_html=True)



# 출처 표기
st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: 0.8rem;'>Data Source: EM-DAT, KOR Disaster Stats</p>", unsafe_allow_html=True)
