import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math
import time

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

st.markdown("## 🌍 Global Globe")

DEFAULT_METRIC = "Total Occurrences"

# Top 5 disaster types (global frequency)
top_5_disasters = df_raw["Disaster Type"].value_counts().nlargest(5).index.tolist()

# -----------------------------
# session_state init
# -----------------------------
if "globe_metric" not in st.session_state:
    st.session_state["globe_metric"] = DEFAULT_METRIC

if "globe_types" not in st.session_state:
    st.session_state["globe_types"] = top_5_disasters

if "globe_render_key" not in st.session_state:
    st.session_state["globe_render_key"] = 0

# -----------------------------
# Handle globe reset (핵심)
# -----------------------------
if st.session_state.get("globe_reset", False):
    st.session_state["globe_types"] = top_5_disasters
    st.session_state["globe_metric"] = DEFAULT_METRIC
    st.session_state["globe_reset"] = False

# -----------------------------
# Reset button
# -----------------------------
col_metric, col_reset = st.columns([8, 2])

with col_metric:
    metric_choice = st.radio(
        "Select Visual Metric:",
        ("Total Occurrences", "Total Deaths", "Total Affected"),
        horizontal=True,
        key="globe_metric"
    )

with col_reset:
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    if st.button("↩ Reset Globe", key="btn_reset_globe"):

        # 기존 state 제거
        for k in ["globe_types", "globe_metric"]:
            if k in st.session_state:
                del st.session_state[k]

        # ✅ 체크박스 상태도 같이 제거
        for t in top_5_disasters:
            chk_key = f"globe_type_{t}"
            if chk_key in st.session_state:
                del st.session_state[chk_key]

        # plotly 재렌더
        st.session_state["globe_render_key"] += 1

        st.rerun()




# -----------------------------
# Controls (types + metric)
# -----------------------------
st.caption("Select Disaster Types (Top 5)")

cols = st.columns(len(top_5_disasters))
selected_types = []

# session_state에 저장된 선택값(기본: top_5_disasters)
current_selected = set(st.session_state.get("globe_types", top_5_disasters))

for col, t in zip(cols, top_5_disasters):
    with col:
        checked = st.checkbox(
            t,
            value=(t in current_selected),
            key=f"globe_type_{t}"   # 각 체크박스 key 유니크
        )
        if checked:
            selected_types.append(t)

# 선택 결과를 globe_types에 다시 저장 (다음 rerun에도 유지)
st.session_state["globe_types"] = selected_types

if len(selected_types) == 0:
    st.warning("재해 유형을 최소 1개 이상 선택해주세요.")
    st.stop()


# 0개 선택이면 안내하고 중단 (오류 방지)
if len(selected_types) == 0:
    st.warning("재해 유형을 최소 1개 이상 선택해주세요.")
    st.stop()

# -----------------------------
# Filter data by selected types
# -----------------------------
df_globe = df_raw[df_raw["Disaster Type"].isin(selected_types)].copy()

# -----------------------------
# Metric mapping
# -----------------------------
if metric_choice == "Total Occurrences":
    color_scale = "Oranges"
    metric_mode = "count"   # count rows
    value_col = None
elif metric_choice == "Total Deaths":
    color_scale = "Reds"
    metric_mode = "sum"
    value_col = "Total Deaths"
else:
    color_scale = "YlOrBr"
    metric_mode = "sum"
    value_col = "Total Affected"

# -----------------------------
# Build ALL-years data for animation (Year slider INSIDE Plotly)
# -----------------------------
# 1) compute region-year value
# 데이터셋 기준 최대 연도 - 1까지만 사용
MAX_YEAR = df_globe["Start Year"].max() - 1
df_globe = df_globe[df_globe["Start Year"] <= MAX_YEAR]

if metric_mode == "count":
    region_year = (
        df_globe.groupby(["Start Year", "Region"])
        .size()
        .reset_index(name="Value")
    )
else:
    region_year = (
        df_globe.groupby(["Start Year", "Region"])[value_col]
        .sum()
        .reset_index(name="Value")
    )

# 2) ISO mapping: assign each country's ISO to its region value
df_iso_mapping = df_raw[["Region", "ISO", "Country"]].drop_duplicates()

map_data_all = (
    df_iso_mapping.merge(region_year, on="Region", how="left")
    .fillna({"Value": 0})
)

# -----------------------------
# Fixed color scale across ALL years (robust: 95% cap)
# -----------------------------
min_scale = 0
max_scale = float(region_year["Value"].quantile(0.95)) if len(region_year) else 1.0
if max_scale <= 0:
    max_scale = 1.0

# -----------------------------
# Globe figure (animation_frame keeps rotation while changing year)
# -----------------------------
fig_globe = px.choropleth(
    map_data_all,
    locations="ISO",
    color="Value",
    hover_name="Region",
    hover_data={"ISO": False, "Country": True, "Value": True, "Start Year": True},
    color_continuous_scale=color_scale,
    range_color=(min_scale, max_scale),
    projection="orthographic",
    animation_frame="Start Year",      # year slider inside plotly (no Streamlit rerun)
    template="plotly_dark",
    title=f"Global {metric_choice} — {', '.join(selected_types)}"
)

# geo 스타일을 모든 animation frame에 강제 적용
fig_globe.update_geos(
    showframe=False,
    showcoastlines=True,
    coastlinecolor="rgba(220,220,220,0.35)",

    showocean=True,
    oceancolor="rgb(30, 55, 90)",   # 🌊 바다 색 (확실히 보이게)

    showlakes=True,
    lakecolor="rgb(30, 55, 90)",

    bgcolor="rgb(12, 14, 20)",      # 🪐 지구 바깥 배경
)

# Make the play button a bit nicer + keep layout clean
uirevision = None if st.session_state.get("globe_reset", False) else "globe_anim"

fig_globe.update_layout(
    height=700,
    margin={"r":0, "t":60, "l":0, "b":0},
    paper_bgcolor="rgb(10,10,15)",
    plot_bgcolor="rgb(10,10,15)",
    coloraxis_colorbar=dict(
        title=dict(text=metric_choice, side="right"),
        x=0.9,
    ),
    uirevision=uirevision
)

fig_globe.update_geos(
    showland=True,
    landcolor="rgba(240,240,240,0.15)"
)

# --------------------------------------------------
# Reset 시 연도 슬라이더를 항상 '첫 연도'로 시작
# --------------------------------------------------
if fig_globe.layout.sliders and len(fig_globe.layout.sliders) > 0:
    fig_globe.layout.sliders[0].active = 0

# Optional: slow down default animation speed (Play button)
# (Plotly stores this in updatemenus[0].buttons[0].args[1])
if fig_globe.layout.updatemenus and len(fig_globe.layout.updatemenus) > 0:
    try:
        fig_globe.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 600
        fig_globe.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 200
    except Exception:
        pass

st.plotly_chart(
    fig_globe,
    use_container_width=True,
    config={"scrollZoom": True},
    key=f"globe_{st.session_state['globe_render_key']}"
)

# -----------------------------------------------------------------------------
# 3_2. Area plot (Global Trend by Disaster Type)
# -----------------------------------------------------------------------------

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
max_y = int(df_occ["Start Year"].max())-1
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

st.markdown("---")
st.subheader("☠️ Disaster Death Toll by Type Over Time")

# -----------------------------
# 0) 상위 토글: Region 선택 (Global 포함)
# -----------------------------
regions = ["Global"] + sorted(df_raw["Region"].dropna().unique().tolist())
selected_region = st.radio(
    "Select Region (Deaths)",
    regions,
    horizontal=True,
    index=0,
    key="region_deaths"
)

# Region 필터링
if selected_region == "Global":
    df_region = df_raw.copy()
else:
    df_region = df_raw[df_raw["Region"] == selected_region].copy()

# -----------------------------
# 1) 선택된 Region 기준 Top 5 (사망자 합계 기준)
# -----------------------------
TOP_N = 5
top_types = (
    df_region.groupby("Disaster Type")["Total Deaths"]
    .sum()
    .sort_values(ascending=False)
    .head(TOP_N)
    .index
    .tolist()
)

# 데이터 없는 경우 방어
if len(top_types) == 0:
    st.warning("해당 Region에는 인명 피해 데이터가 없습니다.")
    st.stop()

# -----------------------------
# 2) 하위 토글: Top 5 가로 체크박스
# -----------------------------
st.caption("Select Disaster Types (Top 5 by Total Deaths)")

palette = px.colors.qualitative.Plotly
color_map = {t: palette[i % len(palette)] for i, t in enumerate(top_types)}

cols = st.columns(len(top_types))
selected_types = []

for col, t in zip(cols, top_types):
    with col:
        if st.checkbox(t, value=True, key=f"chk_deaths_{selected_region}_{t}"):
            selected_types.append(t)

# 아무것도 선택 안 하면 안내만
if len(selected_types) == 0:
    st.info("👆 최소 1개 이상의 재해 유형을 선택해야 그래프가 표시됩니다.")
    st.stop()

# -----------------------------
# 3) 집계: (연도 x 유형) 사망자 합계
# -----------------------------
df_deaths = (
    df_region[df_region["Disaster Type"].isin(selected_types)]
    .groupby(["Start Year", "Disaster Type"])["Total Deaths"]
    .sum()
    .reset_index()
)

# 순서 고정 (Top 5 기준)
ordered_selected = [t for t in top_types if t in selected_types]
df_deaths["Disaster Type"] = pd.Categorical(
    df_deaths["Disaster Type"],
    categories=ordered_selected,
    ordered=True
)
df_deaths = df_deaths.sort_values(["Start Year", "Disaster Type"])

# -----------------------------
# 4) 연도 범위 슬라이더
# -----------------------------
min_y = int(df_deaths["Start Year"].min())
max_y = int(df_deaths["Start Year"].max())
year_range = st.slider(
    "Year Range (Deaths)",
    min_y,
    max_y,
    (min_y, max_y),
    key="year_range_deaths"
)

df_deaths = df_deaths[
    (df_deaths["Start Year"] >= year_range[0]) &
    (df_deaths["Start Year"] <= year_range[1])
]

# -----------------------------
# 5) Plotly Area plot (사망자)
# -----------------------------
fig_deaths = px.area(
    df_deaths,
    x="Start Year",
    y="Total Deaths",
    color="Disaster Type",
    template="plotly_dark",
    category_orders={"Disaster Type": ordered_selected},
    color_discrete_map=color_map,
    labels={
        "Start Year": "Year",
        "Total Deaths": "Total Deaths",
        "Disaster Type": "Type"
    },
    title=f"{selected_region} — Disaster Death Toll Over Time"
)

# legend가 그래프 가리지 않게
fig_deaths.update_layout(
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
        xanchor="center"
    ),
    margin=dict(l=20, r=20, t=150, b=20)
)

st.plotly_chart(fig_deaths, use_container_width=True)

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
    kor_type = st.selectbox("Select Disaster Type", top_5_kor, key="kor_type_pic")




# 선택된 데이터 값 가져오기
subset = df_kor_filtered[
    (df_kor_filtered['Year'] == kor_year) & 
    (df_kor_filtered['Disaster Type'] == kor_type)
]
death_count = int(subset['Total_Deaths'].sum()) if not subset.empty else 0

# -----------------------------
# 컨텍스트 변경 시 상태 초기화 (잔상 제거 핵심)
# -----------------------------
current_context = f"{kor_year}_{kor_type}"

if "pictogram_context" not in st.session_state:
    st.session_state.pictogram_context = current_context

if st.session_state.pictogram_context != current_context:
    st.session_state.pictogram_context = current_context
    st.session_state.pictogram_step = 0
    st.session_state.pictogram_active = False

# -----------------------------
# 상태 초기화
# -----------------------------
if "pictogram_step" not in st.session_state:
    st.session_state.pictogram_step = 0

if "pictogram_active" not in st.session_state:
    st.session_state.pictogram_active = False

# -----------------------------
# 레이아웃
# -----------------------------
col_pic_left, col_pic_right = st.columns([1, 3])

# =========================================================
# LEFT: 컨트롤 / 버튼
# =========================================================
with col_pic_left:
    st.markdown("<div style='text-align:center; margin-top:40px;'>", unsafe_allow_html=True)
    st.markdown(f"<h2>{death_count:,} Deaths</h2>", unsafe_allow_html=True)

    speed = st.slider(
        "Animation speed",
        0.005,
        0.05,
        0.015,
        step=0.005,
        key="pic_speed"
    )

    cA, cB = st.columns(2)
    with cA:
        play = st.button("▶ Play", key="pic_play")
    with cB:
        reset = st.button("↩ Reset", key="pic_reset")

    st.markdown("</div>", unsafe_allow_html=True)
    st.info("1 Block = 1 Person")

# =========================================================
# RIGHT: Pictogram (항상 기본 그리드 표시)
# =========================================================
with col_pic_right:
    UNIT_PER_ICON = 1
    base_icons = 108
    active_icons = math.ceil(death_count / UNIT_PER_ICON)

    # 기본 108, 초과 시 확장
    total_icons = max(base_icons, active_icons)

    # 색상 결정
    if death_count == 0:
        active_class = ""
    elif death_count > 100:
        active_class = "active-red"
    elif death_count > 50:
        active_class = "active-orange"
    else:
        active_class = "active-yellow"

    holder = st.empty()

    # -----------------------------
    # 렌더 함수
    # -----------------------------
    def render(step: int):
        step = max(0, min(step, active_icons))
        icon_html = ""
        for i in range(total_icons):
            cls = active_class if i < step else ""
            icon_html += f'<div class="person-icon {cls}"></div>'

        holder.markdown(
            f"""
            <div class="person-grid">
                {icon_html}
            </div>
            """,
            unsafe_allow_html=True
        )

    # 항상 기본 그리드부터 렌더
    render(st.session_state.pictogram_step)

    # -----------------------------
    # Reset
    # -----------------------------
    if reset:
        st.session_state.pictogram_step = 0
        st.session_state.pictogram_active = False
        render(0)
        st.stop()

    # -----------------------------
    # Play (항상 0부터 시작)
    # -----------------------------
    if play:
        st.session_state.pictogram_active = True
        st.session_state.pictogram_step = 0

        for step in range(0, active_icons + 1):
            st.session_state.pictogram_step = step
            render(step)
            time.sleep(speed)


# 출처 표기
st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: 0.8rem;'>Data Source: EM-DAT, KOR Disaster Stats</p>", unsafe_allow_html=True)
