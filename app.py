import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math
import time
from plotly.subplots import make_subplots

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

# 고정 색상 매핑: Disaster Type -> Color (한 번 만들면 계속 유지)
palette = (
    px.colors.qualitative.Dark24 +
    px.colors.qualitative.Light24 +
    px.colors.qualitative.Alphabet
)

all_types = sorted(df_raw["Disaster Type"].dropna().unique().tolist())

manual_colors = {
    "Flood": "#1f77b4",
    "Wildfire": "#d62728",
    "Drought": "#8c564b",
    "Storm": "#9467bd",
}

if "DISASTER_COLOR_MAP" not in st.session_state:

    cmap = {}
    used_colors = set(manual_colors.values())
    palette_index = 0

    for t in all_types:

        if t in manual_colors:
            cmap[t] = manual_colors[t]

        else:
            # manual 색 피하면서 자동 배정
            while palette[palette_index % len(palette)] in used_colors:
                palette_index += 1

            cmap[t] = palette[palette_index % len(palette)]
            used_colors.add(cmap[t])
            palette_index += 1

    st.session_state["DISASTER_COLOR_MAP"] = cmap

DISASTER_COLOR_MAP = st.session_state["DISASTER_COLOR_MAP"]


#FIRST LOAD: checkbox key가 없으면 기본 True로 세팅
for t in top_5_disasters:
    k = f"globe_type_{t}"
    if k not in st.session_state:
        st.session_state[k] = True
# -----------------------------
# session_state init
# -----------------------------
if "globe_metric" not in st.session_state:
    st.session_state["globe_metric"] = DEFAULT_METRIC

if "globe_types" not in st.session_state:
    st.session_state["globe_types"] = top_5_disasters

if "globe_render_key" not in st.session_state:
    st.session_state["globe_render_key"] = 0

# reset flag init
if "globe_reset" not in st.session_state:
    st.session_state["globe_reset"] = False

# -----------------------------
# Handle globe reset (체크박스까지 강제 초기화) - 체크박스 만들기 전에!
# -----------------------------
if st.session_state["globe_reset"]:
    # Top5는 True로 (초기 선택)
    for t in top_5_disasters:
        st.session_state[f"globe_type_{t}"] = True    

    # 3) 내부 리스트도 초기화
    st.session_state["globe_types"] = top_5_disasters

    # 4) metric도 초기화
    st.session_state["globe_metric"] = DEFAULT_METRIC

    # 5) reset 종료
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
        # del 하지 말고 reset flag만 올리기
        st.session_state["globe_reset"] = True

        # plotly 재렌더 키 증가
        st.session_state["globe_render_key"] += 1
        st.rerun()

# -----------------------------
# Controls (types) - value를 직접 넣지 말고 session_state(checkbox key)에 맡기기
# -----------------------------
st.caption("Select Disaster Types (Top 5)")

cols = st.columns(len(top_5_disasters))
selected_types = []

for col, t in zip(cols, top_5_disasters):
    with col:
        checked = st.checkbox(
            t,
            key=f"globe_type_{t}"
        )
        if checked:
            selected_types.append(t)

# 선택 결과를 globe_types에 저장
st.session_state["globe_types"] = selected_types

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
# Insight 1: Global (Occurrences=Bar, Deaths=Line) with Top5 toggle + TOTAL mode
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 재해는 늘었지만, 인류는 강해졌다 (Decoupling)")

# Global 기준 발생 건수 Top5
top5_global = (
    df_raw["Disaster Type"]
    .value_counts()
    .nlargest(5)
    .index
    .tolist()
)

# 첫 로드: 기본값 Top5 모두 True
for t in top5_global:
    k = f"ins1_type_{t}"
    if k not in st.session_state:
        st.session_state[k] = True

# TOTAL 모드 토글(추가)
if "ins1_total_mode" not in st.session_state:
    st.session_state["ins1_total_mode"] = False

# ---- UI Row: (TOTAL 토글 + 타입 체크박스들)
top_row_l, top_row_r = st.columns([2, 8])

with top_row_l:
    st.checkbox(
        "TOTAL",
        key="ins1_total_mode",
        help="체크하면 선택된 재해들을 합산해서 (발생 1개 bar + 사망 1개 line)로 표시합니다."
    )

with top_row_r:
    st.caption("Select Disaster Types (Top 5 by Global Occurrences)")
    cols = st.columns(len(top5_global))
    ins1_selected = []
    for col, t in zip(cols, top5_global):
        with col:
            if st.checkbox(t, key=f"ins1_type_{t}"):
                ins1_selected.append(t)

if len(ins1_selected) == 0:
    st.warning("재해 유형을 최소 1개 이상 선택해주세요.")
    st.stop()

# 성능: 집계는 캐시 (선택된 타입이 바뀔 때만 다시 계산)
@st.cache_data(show_spinner=False)
def build_insight1_agg(df, selected_types):
    dff = df[df["Disaster Type"].isin(selected_types)].copy()

    occ = (
        dff.groupby(["Start Year", "Disaster Type"])
        .size()
        .reset_index(name="Occurrences")
    )
    deaths = (
        dff.groupby(["Start Year", "Disaster Type"])["Total Deaths"]
        .sum()
        .reset_index(name="Deaths")
    )

    out = occ.merge(deaths, on=["Start Year", "Disaster Type"], how="outer").fillna(0)
    out["Start Year"] = out["Start Year"].astype(int)
    return out.sort_values(["Start Year", "Disaster Type"])

df_ins1 = build_insight1_agg(df_raw, tuple(ins1_selected))

MAX_YEAR_INS1 = df_raw["Start Year"].max() - 1
df_ins1 = df_ins1[df_ins1["Start Year"] <= MAX_YEAR_INS1]

fig_ins1 = make_subplots(specs=[[{"secondary_y": True}]])

# =====================================================================
# TOTAL MODE: 선택된 재해 합산 (bar 1개 + line 1개)
# =====================================================================
if st.session_state["ins1_total_mode"]:
    df_total = (
        df_ins1.groupby("Start Year")[["Occurrences", "Deaths"]]
        .sum()
        .reset_index()
        .sort_values("Start Year")
    )

    fig_ins1.add_trace(
        go.Bar(
            x=df_total["Start Year"],
            y=df_total["Occurrences"],
            name="Total Occurrences",
            opacity=0.70,
        ),
        secondary_y=False
    )

    fig_ins1.add_trace(
        go.Scatter(
            x=df_total["Start Year"],
            y=df_total["Deaths"],
            name="Total Deaths",
            mode="lines+markers",
            line=dict(width=2),
            marker=dict(size=4),
        ),
        secondary_y=True
    )

    fig_ins1.update_layout(barmode="overlay")  # bar 1개라 overlay가 깔끔

# =====================================================================
# TYPE MODE: 재해별 (stacked bar + 재해별 line)  (기존 방식)
# =====================================================================
else:
    # 1) 발생 건수(Bar) - 재해별 색 고정 (stacked)
    for t in ins1_selected:
        df_t = df_ins1[df_ins1["Disaster Type"] == t]
        fig_ins1.add_trace(
            go.Bar(
                x=df_t["Start Year"],
                y=df_t["Occurrences"],
                name=t,
                marker=dict(color=DISASTER_COLOR_MAP.get(t, "#888")),
                opacity=0.70,
            ),
            secondary_y=False
        )

    # 2) 인명피해(Line) - 같은 색으로 재해별 라인
    for t in ins1_selected:
        df_t = df_ins1[df_ins1["Disaster Type"] == t]
        fig_ins1.add_trace(
            go.Scatter(
                x=df_t["Start Year"],
                y=df_t["Deaths"],
                name=f"{t} (Deaths)",
                mode="lines+markers",
                line=dict(color=DISASTER_COLOR_MAP.get(t, "#888"), width=2),
                marker=dict(size=4),
            ),
            secondary_y=True
        )

    fig_ins1.update_layout(barmode="stack")  # 막대는 누적

# ---- 공통 레이아웃
fig_ins1.update_layout(
    template="plotly_dark",
    height=520,
    margin=dict(l=20, r=20, t=60, b=20),
    xaxis_title="Year",
    legend=dict(
        orientation="h",
        y=1.15,
        x=0.0,
        xanchor="left",
        title=dict(text="Type")
    ),
)

fig_ins1.update_yaxes(title_text="발생 건수 (건)", secondary_y=False)
fig_ins1.update_yaxes(title_text="사망자 수 (명)", secondary_y=True)

st.plotly_chart(fig_ins1, use_container_width=True)



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

color_map = DISASTER_COLOR_MAP

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

color_map = DISASTER_COLOR_MAP

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
# Storytelling Interactive Visualization (Step-by-step) — NO WINDOW VERSION
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🧭 Story: 기후 변화는 각 대륙에 어떤 영향을 미쳤을까요?")

# ---- Step state init
if "story_step" not in st.session_state:
    st.session_state["story_step"] = 0

def next_step():
    st.session_state["story_step"] += 1
    st.rerun()

def prev_step():
    st.session_state["story_step"] = max(0, st.session_state["story_step"] - 1)
    st.rerun()

def reset_story():
    # window 관련 키는 없애고, 여기서 쓰는 키들만 정리
    for k in ["story_step", "story_region", "story_year_end", "story_metric_mode"]:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

# ---- Controls row (Back / Reset)
nav_l, nav_c, nav_r = st.columns([2, 6, 2])
with nav_l:
    if st.session_state["story_step"] > 0:
        st.button("⬅ Back", on_click=prev_step)
with nav_r:
    st.button("↩ Reset Story", on_click=reset_story)

# -----------------------------------------------------------------------------
# Common helpers for story (cache)  ✅ window 제거 버전
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def story_agg_no_window(df: pd.DataFrame, region: str, year_end: int):
    """
    1970 ~ year_end 전체 추이 집계 (window 제거)
    Returns:
      - summary: disaster type별 전체 합계(occ_total, d_total) — 랭킹용
      - yearly:  (Start Year, Disaster Type) 연도별 추이 (Occurrences, Deaths) — 그래프용
    """
    FIXED_START = 1970

    dff = df.copy()
    if region != "Global":
        dff = dff[dff["Region"] == region]

    dff = dff[(dff["Start Year"] >= FIXED_START) & (dff["Start Year"] <= year_end)]

    summary = (
        dff.groupby("Disaster Type")
        .agg(
            occ_total=("Disaster Type", "size"),
            d_total=("Total Deaths", "sum"),
        )
        .reset_index()
        .sort_values(["occ_total", "d_total"], ascending=False)
    )

    yearly = (
        dff.groupby(["Start Year", "Disaster Type"])
        .agg(
            Occurrences=("Disaster Type", "size"),
            Deaths=("Total Deaths", "sum"),
        )
        .reset_index()
        .sort_values(["Start Year", "Disaster Type"])
    )

    return summary, yearly

# -----------------------------------------------------------------------------
# Step 0: intro
# -----------------------------------------------------------------------------
if st.session_state["story_step"] == 0:
    st.info(
        "이 스토리는 **대륙별로 재해 발생/인명피해가 어떻게 달라졌는지**를 단계적으로 따라가며 탐색합니다.\n\n"
        "➡️ 준비되면 **Start**를 눌러주세요."
    )
    st.button("🚀 Start", on_click=next_step)

# -----------------------------------------------------------------------------
# Step 1: choose continent
# -----------------------------------------------------------------------------
if st.session_state["story_step"] == 1:
    st.markdown("### 1) 먼저, 가장 궁금한 **대륙(Region)** 을 선택해 주세요.")

    regions = ["Global"] + sorted(df_raw["Region"].dropna().unique().tolist())
    if "story_region" not in st.session_state:
        st.session_state["story_region"] = "Global"

    st.session_state["story_region"] = st.radio(
        "Choose Region",
        regions,
        horizontal=True,
        index=regions.index(st.session_state["story_region"]) if st.session_state["story_region"] in regions else 0
    )

    st.button("Next ➜", on_click=next_step)

# -----------------------------------------------------------------------------
# Step 2: choose END year only (start fixed = 1970)  ✅ window UI 제거
# -----------------------------------------------------------------------------
if st.session_state["story_step"] == 2:
    st.markdown("### 2) 어떤 기간을 살펴볼까요?")
    st.caption("시작 연도는 **1970년 고정**이고, 끝 연도만 선택합니다.")

    FIXED_START = 1970
    data_max_minus1 = int(df_raw["Start Year"].max()) - 1
    max_year = min(2025, data_max_minus1)

    if "story_year_end" not in st.session_state:
        st.session_state["story_year_end"] = max_year

    col1, col2 = st.columns([6, 4])

    with col1:
        st.session_state["story_year_end"] = st.slider(
            f"End year (Start fixed at {FIXED_START})",
            min_value=FIXED_START,
            max_value=max_year,
            value=st.session_state["story_year_end"],
            step=1
        )
        st.caption(f"Selected range: **{FIXED_START}–{st.session_state['story_year_end']}**")

    with col2:
        if "story_metric_mode" not in st.session_state:
            st.session_state["story_metric_mode"] = "Occurrences"

        st.session_state["story_metric_mode"] = st.radio(
            "Focus",
            ["Occurrences", "Deaths"],
            horizontal=True,
            index=0 if st.session_state["story_metric_mode"] == "Occurrences" else 1
        )

    st.button("Next ➜", on_click=next_step)

# -----------------------------------------------------------------------------
# Step 3: show "top impact" + charts (Top5 + trend)  ✅ window 비교 제거
# -----------------------------------------------------------------------------
if st.session_state["story_step"] == 3:
    region = st.session_state.get("story_region", "Global")
    year_end = st.session_state.get("story_year_end", int(df_raw["Start Year"].max()) - 1)
    focus = st.session_state.get("story_metric_mode", "Occurrences")

    df_sum, df_yearly = story_agg_no_window(df_raw, region, year_end)

    if df_sum.empty:
        st.warning("선택한 조건에서 표시할 데이터가 없습니다.")
        st.stop()

    if focus == "Occurrences":
        df_rank = df_sum.sort_values("occ_total", ascending=False)
        metric_title = "발생 건수"
        value_col = "occ_total"
    else:
        df_rank = df_sum.sort_values("d_total", ascending=False)
        metric_title = "사망자 수"
        value_col = "d_total"

    top = df_rank.iloc[0]
    top_type = top["Disaster Type"]
    top_val = int(top[value_col])

    st.markdown("### 3) 어떤 재해가 가장 큰 영향을 미쳤을까요?")
    st.success(
        f"**{region}**에서 **1970–{year_end}** 동안\n\n"
        f"➡️ **{top_type}**의 **{metric_title}**가 가장 큽니다.\n\n"
        f"- 합계: **{top_val:,}**"
    )

    # --- Top 5 (Animated bar by year)
    topN = 5
    view = df_rank.head(topN).copy()
    top_types = view["Disaster Type"].tolist()

    # 연도별(1970~year_end) Top5만 집계
    dff_top = df_yearly[df_yearly["Disaster Type"].isin(top_types)].copy()

    # focus에 따라 y값 선택
    if focus == "Occurrences":
        y_col = "Occurrences"
        title = f"Top {topN} ({metric_title}) — {region} (1970–{year_end})"
    else:
        y_col = "Deaths"
        title = f"Top {topN} ({metric_title}) — {region} (1970–{year_end})"

    # ✅ 각 연도에 Top5 타입이 모두 보이도록 0으로 채우기 (막대가 5개 항상 뜨게)
    years = sorted(dff_top["Start Year"].unique().tolist())
    full_index = pd.MultiIndex.from_product([years, top_types], names=["Start Year", "Disaster Type"])
    dff_anim = (
        dff_top.set_index(["Start Year", "Disaster Type"])[[y_col]]
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    # ✅ 애니메이션 바차트 (연도 슬라이더 + 재생 버튼 자동 포함)
    fig_top_anim = px.bar(
        dff_anim,
        x="Disaster Type",
        y=y_col,
        color="Disaster Type",
        animation_frame="Start Year",          # <- 핵심: 연도별 애니메이션
        category_orders={"Disaster Type": top_types},  # <- Top5 순서 고정
        color_discrete_map=DISASTER_COLOR_MAP,         # <- 기존 색상 맵 통일
        template="plotly_dark",
        title=title
    )
    # ✅ 애니메이션 속도 조절
    if fig_top_anim.layout.updatemenus:
        try:
            fig_top_anim.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 30
            fig_top_anim.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 10
            fig_top_anim.layout.updatemenus[0].buttons[0].args[1]["transition"]["easing"] = "linear"

        except Exception:
            pass

    # ✅ Autoscale을 처음부터 적용
    y_max = dff_anim[y_col].max() * 1.15
    fig_top_anim.update_yaxes(range=[0, y_max])

    # 보기 좋게 레이아웃 조정
    fig_top_anim.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=70, b=20),
        xaxis_title="",
        yaxis_title=metric_title,
        showlegend=False,  # 막대 자체가 색으로 구분되니 legend는 꺼도 깔끔
    )

    # ✅ 애니메이션 속도(재생 버튼 눌렀을 때)
    # (Plotly는 play 버튼 설정이 updatemenus에 들어감)
    if fig_top_anim.layout.updatemenus and len(fig_top_anim.layout.updatemenus) > 0:
        try:
            fig_top_anim.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 500
            fig_top_anim.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 200
        except Exception:
            pass

    # (선택) 첫 프레임을 1970으로 고정
    if fig_top_anim.layout.sliders and len(fig_top_anim.layout.sliders) > 0:
        fig_top_anim.layout.sliders[0].active = 0

    st.plotly_chart(fig_top_anim, use_container_width=True)

    # --- Trend line for Top 5 types
    st.markdown("#### 1970년부터 선택한 연도까지, 연도별 추이")

    dff = df_yearly[df_yearly["Disaster Type"].isin(view["Disaster Type"])].copy()

    if focus == "Occurrences":
        fig_trend = px.line(
            dff,
            x="Start Year",
            y="Occurrences",
            color="Disaster Type",
            color_discrete_map=DISASTER_COLOR_MAP,
            template="plotly_dark",
            title=f"{region} — Trend (Occurrences) 1970–{year_end}"
        )
    else:
        fig_trend = px.line(
            dff,
            x="Start Year",
            y="Deaths",
            color="Disaster Type",
            color_discrete_map=DISASTER_COLOR_MAP,
            template="plotly_dark",
            title=f"{region} — Trend (Deaths) 1970–{year_end}"
        )

    # top 1 강조
    for tr in fig_trend.data:
        if tr.name == top_type:
            tr.line.width = 4
        else:
            tr.line.width = 2
            tr.opacity = 0.55

    fig_trend.update_layout(height=420, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig_trend, use_container_width=True)

    st.info("➡️ 다음 단계에서 특정 재해를 골라 더 자세히 볼 수 있어요.")
    st.button("Next ➜", on_click=next_step)

# -----------------------------------------------------------------------------
# Step 4: user chooses a disaster and explores (Bar=Occurrences, Line=Deaths)
# -----------------------------------------------------------------------------
if st.session_state["story_step"] == 4:

    st.markdown("### 4) 이제 특정 재해를 골라 더 자세히 볼까요?")

    region = st.session_state.get("story_region", "Global")

    cand = sorted(df_raw["Disaster Type"].dropna().unique().tolist())
    choice = st.selectbox("Pick a disaster type", cand)

    # -----------------------------
    # 연도별 집계
    # -----------------------------
    d = df_raw.copy()

    if region != "Global":
        d = d[d["Region"] == region]

    d = (
        d[d["Disaster Type"] == choice]
        .groupby("Start Year")
        .agg(
            Occurrences=("Disaster Type", "size"),
            Deaths=("Total Deaths", "sum")
        )
        .reset_index()
        .sort_values("Start Year")
    )

    # 최대 연도 -1
    MAXY = int(df_raw["Start Year"].max()) - 1
    d = d[d["Start Year"] <= MAXY]

    # -----------------------------
    # Animated 그래프 함수
    # -----------------------------
    def make_anim(d):

        years = d["Start Year"].tolist()

        fig = go.Figure()

        # 초기 데이터
        d0 = d[d["Start Year"] <= years[0]]

        fig.add_bar(
            x=d0["Start Year"],
            y=d0["Occurrences"],
            name="Occurrences",
            marker=dict(color=DISASTER_COLOR_MAP.get(choice, "#1f77b4")),
            opacity=0.65,
            yaxis="y"
        )

        fig.add_scatter(
            x=d0["Start Year"],
            y=d0["Deaths"],
            name="Deaths",
            mode="lines+markers",
            line=dict(color=DISASTER_COLOR_MAP.get(choice, "#1f77b4"), width=3),
            yaxis="y2"
        )

        # frames 생성
        frames = []
        for y in years:

            dy = d[d["Start Year"] <= y]

            frames.append(
                go.Frame(
                    name=str(y),
                    data=[
                        go.Bar(x=dy["Start Year"], y=dy["Occurrences"]),
                        go.Scatter(x=dy["Start Year"], y=dy["Deaths"])
                    ]
                )
            )

        fig.frames = frames

        # 슬라이더
        steps = []
        for y in years:
            steps.append(
                dict(
                    method="animate",
                    args=[[str(y)],
                          dict(frame=dict(duration=80, redraw=True),
                               transition=dict(duration=40))],
                    label=str(y)
                )
            )

        fig.update_layout(
            template="plotly_dark",
            height=520,
            title=f"{region} — {choice}",
            sliders=[dict(active=0, steps=steps)],
            updatemenus=[
                dict(
                    type="buttons",
                    buttons=[
                        dict(
                            label="▶ Play",
                            method="animate",
                            args=[None, dict(frame=dict(duration=80, redraw=True))]
                        )
                    ]
                )
            ],
            yaxis=dict(title="Occurrences"),
            yaxis2=dict(title="Deaths", overlaying="y", side="right")
        )

        return fig

    fig_anim = make_anim(d)

    st.plotly_chart(fig_anim, use_container_width=True)

    st.success("✅ 스토리 완료!")



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
    base_icons = 430 #86
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
