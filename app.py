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
    page_title="Remapping Global Disasters",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")

@st.cache_data
def load_data():
    df = pd.read_csv("data/public_emdat_1970_2020.csv")
    df_korea = pd.read_csv("data/df_korea.csv")
    
    df = df[df['Start Year'].notna()]
    df['Start Year'] = df['Start Year'].astype(int)
    
    cols_to_fix = ['Total Deaths', 'Total Affected', 'Total Damage (\'000 US$)']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    if 'Start Year' in df_korea.columns:
        df_korea = df_korea.rename(columns={'Start Year': 'Year'})
    if 'Total Deaths' in df_korea.columns:
        df_korea = df_korea.rename(columns={'Total Deaths': 'Total_Deaths'})
    
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
st.markdown(
    """
    <div style="text-align:center; margin-top: 6px; margin-bottom: 6px;">
        <div style="font-size: 3.4rem; font-weight: 900; line-height: 1.05; color: #ff3b3b;">
            Remapping Global Disasters 🌍
        </div>
        <div style="font-size: 1.35rem; font-weight: 600; opacity: 0.85; margin-top: 8px;">
            EM-DAT 데이터를 기반으로 전 세계 재해의 발생 위치, 유형, 빈도, 피해 규모를 시공간적으로 살펴봅니다.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# -----------------------------------------------------------------------------
# 3. GLOBAL SECTION: The Globe
# -----------------------------------------------------------------------------

st.markdown("## 🌍 섹션 1. 대륙별 Top 5 재해 발생 현황")
st.markdown("##### 대륙별 재해 발생과 피해 규모 한눈에 보기")

DEFAULT_METRIC = "발생 건수"

top_5_disasters = df_raw["Disaster Type"].value_counts().nlargest(5).index.tolist()

palette = (
    px.colors.qualitative.Plotly +
    px.colors.qualitative.Set1 +
    px.colors.qualitative.Set2 +
    px.colors.qualitative.Safe
)

all_types = sorted(df_raw["Disaster Type"].dropna().unique().tolist())

manual_colors = {
    "Flood": "#4c78a8",
    "Storm": "#f58518",
    "Drought": "#e45756",
    "Wildfire": "#ffbf00",
    "Earthquake": "#72b7b2",
    "Landslide": "#54a24b",
    "Extreme temperature": "#b279a2",
    "Epidemic": "#ff9da6",
}

if "DISASTER_COLOR_MAP" not in st.session_state:
    cmap = {}
    used_colors = set(manual_colors.values())
    palette_index = 0

    for t in all_types:
        if t in manual_colors:
            cmap[t] = manual_colors[t]
        else:
            while palette[palette_index % len(palette)] in used_colors:
                palette_index += 1
            cmap[t] = palette[palette_index % len(palette)]
            used_colors.add(cmap[t])
            palette_index += 1

    st.session_state["DISASTER_COLOR_MAP"] = cmap

DISASTER_COLOR_MAP = st.session_state["DISASTER_COLOR_MAP"]

for t in top_5_disasters:
    k = f"globe_type_{t}"
    if k not in st.session_state:
        st.session_state[k] = True

if "globe_metric" not in st.session_state:
    st.session_state["globe_metric"] = DEFAULT_METRIC

if "globe_types" not in st.session_state:
    st.session_state["globe_types"] = top_5_disasters

if "globe_render_key" not in st.session_state:
    st.session_state["globe_render_key"] = 0

if "globe_reset" not in st.session_state:
    st.session_state["globe_reset"] = False

if st.session_state["globe_reset"]:
    for t in top_5_disasters:
        st.session_state[f"globe_type_{t}"] = True    

    st.session_state["globe_types"] = top_5_disasters
    st.session_state["globe_metric"] = DEFAULT_METRIC
    st.session_state["globe_reset"] = False

col_metric, col_reset = st.columns([8, 2])

with col_metric:
    metric_choice = st.radio(
        "시각화 지표 선택:",
        ("발생 건수", "사망자 수", "피해 인구"),
        horizontal=True,
        key="globe_metric"
    )

with col_reset:
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    if st.button("↩ 지구본 초기화", key="btn_reset_globe"):
        st.session_state["globe_reset"] = True
        st.session_state["globe_render_key"] += 1
        st.rerun()

st.caption("재해 유형 선택 (Top 5)")

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

st.session_state["globe_types"] = selected_types

if len(selected_types) == 0:
    st.warning("재해 유형을 최소 1개 이상 선택해주세요.")
    st.stop()

df_globe = df_raw[df_raw["Disaster Type"].isin(selected_types)].copy()

if metric_choice == "발생 건수":
    color_scale = "Oranges"
    metric_mode = "count"
    value_col = None
elif metric_choice == "사망자 수":
    color_scale = "Reds"
    metric_mode = "sum"
    value_col = "Total Deaths"
else:
    color_scale = "YlOrBr"
    metric_mode = "sum"
    value_col = "Total Affected"

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

df_iso_mapping = df_raw[["Region", "ISO", "Country"]].drop_duplicates()

map_data_all = (
    df_iso_mapping.merge(region_year, on="Region", how="left")
    .fillna({"Value": 0})
)

min_scale = 0
max_scale = float(region_year["Value"].quantile(0.95)) if len(region_year) else 1.0
if max_scale <= 0:
    max_scale = 1.0

fig_globe = px.choropleth(
    map_data_all,
    locations="ISO",
    color="Value",
    hover_name="Region",
    hover_data={"ISO": False, "Country": True, "Value": True, "Start Year": True},
    color_continuous_scale=color_scale,
    range_color=(min_scale, max_scale),
    projection="orthographic",
    animation_frame="Start Year",
    template="plotly_dark",
    title=f"전 세계 {metric_choice} — {', '.join(selected_types)}"
)

fig_globe.update_geos(
    showframe=False,
    showcoastlines=True,
    coastlinecolor="rgba(220,220,220,0.35)",
    showocean=True,
    oceancolor="rgb(30, 55, 90)",
    showlakes=True,
    lakecolor="rgb(30, 55, 90)",
    bgcolor="rgb(12, 14, 20)",
)

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

if fig_globe.layout.sliders and len(fig_globe.layout.sliders) > 0:
    fig_globe.layout.sliders[0].active = 0

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

# 섹션 1 인사이트
st.info(
    "**💡 인사이트**\n\n"
    "재해는 단순히 '많이 발생하는가'보다, 어디에서 얼마나 큰 피해로 이어지는가가 훨씬 중요합니다.\n\n"
    "같은 재해라도 대륙에 따라 피해 양상이 극명하게 달라집니다."
)

# -----------------------------------------------------------------------------
# Insight 2: Global (Occurrences=Bar, Deaths=Line) with Top5 toggle + TOTAL mode
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 섹션 2. 글로벌 Top 5 재해 발생 수 vs 사망자 수 추이")
st.markdown("##### 재해는 늘지만, 사망자는 줄어들고 있다?")

top5_global = (
    df_raw["Disaster Type"]
    .value_counts()
    .nlargest(5)
    .index
    .tolist()
)

for t in top5_global:
    k = f"ins1_type_{t}"
    if k not in st.session_state:
        st.session_state[k] = True

if "ins1_total_mode" not in st.session_state:
    st.session_state["ins1_total_mode"] = False

st.caption("재해 유형 선택 (발생 건수 기준 Top 5)")

# 전체 합산 + Top 5 체크박스를 한 줄에 배치
cols = st.columns(len(top5_global) + 1)

# 첫 번째 컬럼: 전체 합산
with cols[0]:
    st.checkbox(
        "전체 합산",
        key="ins1_total_mode",
        help="체크하면 선택된 재해들을 합산해서 (발생 1개 bar + 사망 1개 line)로 표시합니다."
    )

# 나머지 컬럼: Top 5 재해 유형
ins1_selected = []
for i, t in enumerate(top5_global):
    with cols[i + 1]:
        if st.checkbox(t, key=f"ins1_type_{t}"):
            ins1_selected.append(t)

if len(ins1_selected) == 0:
    st.warning("재해 유형을 최소 1개 이상 선택해주세요.")
    st.stop()

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
df_ins1 = df_ins1[df_ins1["Start Year"] != 1970]

fig_ins1 = make_subplots(specs=[[{"secondary_y": True}]])

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
            name="전체 발생 건수",
            opacity=0.70,
        ),
        secondary_y=False
    )

    fig_ins1.add_trace(
        go.Scatter(
            x=df_total["Start Year"],
            y=df_total["Deaths"],
            name="전체 사망자 수",
            mode="lines+markers",
            line=dict(width=4),
            marker=dict(size=4),
        ),
        secondary_y=True
    )

    fig_ins1.update_layout(barmode="overlay")

else:
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

    for t in ins1_selected:
        df_t = df_ins1[df_ins1["Disaster Type"] == t]
        fig_ins1.add_trace(
            go.Scatter(
                x=df_t["Start Year"],
                y=df_t["Deaths"],
                name=f"{t} (사망자)",
                mode="lines+markers",
                line=dict(color=DISASTER_COLOR_MAP.get(t, "#888"), width=4),
                marker=dict(size=4),
            ),
            secondary_y=True
        )

    fig_ins1.update_layout(barmode="stack")

fig_ins1.update_layout(
    template="plotly_dark",
    height=520,
    margin=dict(l=20, r=20, t=60, b=20),
    xaxis_title="연도",
    legend=dict(
        orientation="h",
        y=1.15,
        x=0.0,
        xanchor="left",
        title=dict(text="유형")
    ),
)

fig_ins1.update_yaxes(title_text="발생 건수 (건)", secondary_y=False)
fig_ins1.update_yaxes(title_text="사망자 수 (명)", secondary_y=True)

st.plotly_chart(fig_ins1, use_container_width=True)

# 섹션 2 인사이트
st.info(
    "**💡 인사이트**\n\n"
    "이는 재해 발생과 인명 피해가 점차 분리(decoupling)되고 있음을 의미합니다.\n\n"
    "조기 경보 시스템, 인프라 개선, 의료·구호 체계의 발전으로 재해의 '치명성'을 낮추는 데 기여하고 있습니다."
)

# -----------------------------------------------------------------------------
# 3_2. Area plot (Global Trend by Disaster Type)
# -----------------------------------------------------------------------------

st.markdown("---")
st.subheader("🌐 섹션 3. 대륙별 Top 5 재해 발생 수 추이")
st.markdown("##### 대륙마다 다른 재해의 얼굴")

regions = ["Global"] + sorted(df_raw["Region"].dropna().unique().tolist())
selected_region = st.radio("대륙 선택", regions, horizontal=True, index=0, key="region_section3")

if selected_region == "Global":
    df_region = df_raw.copy()
else:
    df_region = df_raw[df_raw["Region"] == selected_region].copy()

TOP_N = 5
top_types = (
    df_region["Disaster Type"]
    .value_counts()
    .nlargest(TOP_N)
    .index
    .tolist()
)

if len(top_types) == 0:
    st.warning("해당 대륙에는 표시할 데이터가 없습니다.")
    st.stop()

st.caption("재해 유형 선택 (선택한 대륙의 Top 5)")

color_map = DISASTER_COLOR_MAP

cols = st.columns(len(top_types))
selected_types = []

for col, t in zip(cols, top_types):
    with col:
        if st.checkbox(t, value=True, key=f"chk_{selected_region}_{t}"):
            selected_types.append(t)

if len(selected_types) == 0:
    st.info("👆 최소 1개 이상의 재해 유형을 선택해야 그래프가 표시됩니다.")
    st.stop()

df_occ = (
    df_region[df_region["Disaster Type"].isin(selected_types)]
    .groupby(["Start Year", "Disaster Type"])
    .size()
    .reset_index(name="Occurrences")
)

ordered_selected = [t for t in top_types if t in selected_types]
df_occ["Disaster Type"] = pd.Categorical(
    df_occ["Disaster Type"],
    categories=ordered_selected,
    ordered=True
)
df_occ = df_occ.sort_values(["Start Year", "Disaster Type"])

min_y = int(df_occ["Start Year"].min())
max_y = int(df_occ["Start Year"].max())-1
year_range = st.slider("연도 범위", min_y, max_y, (min_y, max_y))

df_occ = df_occ[(df_occ["Start Year"] >= year_range[0]) & (df_occ["Start Year"] <= year_range[1])]

fig_area = px.area(
    df_occ,
    x="Start Year",
    y="Occurrences",
    color="Disaster Type",
    template="plotly_dark",
    category_orders={"Disaster Type": ordered_selected},
    color_discrete_map=color_map,
    labels={"Start Year": "연도", "Occurrences": "발생 건수", "Disaster Type": "유형"},
    title=f"{selected_region} — 시간에 따른 재해 발생 추이"
)

fig_area.update_traces(opacity=0.7)

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

# 섹션 3 인사이트
st.info(
    "**💡 인사이트**\n\n"
    "이 시각화는 재해가 무작위로 발생하는 것이 아니라,기후대·지형·인구 분포와 강하게 연결되어 있음을 보여줍니다.\n\n"
    "대륙별 재해 패턴은 해당 지역의 자연 및 사회적 특성을 반영합니다."
)

st.markdown("---")
st.subheader("☠️ 섹션 4. 대륙별 Top 5 재해 유형별 사망자 수 추이")
st.markdown("##### '자주'가 아니라 '치명적인' 재해는 무엇인가?")

regions = ["Global"] + sorted(df_raw["Region"].dropna().unique().tolist())
selected_region = st.radio(
    "대륙 선택 (사망자)",
    regions,
    horizontal=True,
    index=0,
    key="region_deaths"
)

if selected_region == "Global":
    df_region = df_raw.copy()
else:
    df_region = df_raw[df_raw["Region"] == selected_region].copy()

TOP_N = 5
top_types = (
    df_region.groupby("Disaster Type")["Total Deaths"]
    .sum()
    .sort_values(ascending=False)
    .head(TOP_N)
    .index
    .tolist()
)

if len(top_types) == 0:
    st.warning("해당 대륙에는 인명 피해 데이터가 없습니다.")
    st.stop()

st.caption("재해 유형 선택 (사망자 합계 기준 Top 5)")

color_map = DISASTER_COLOR_MAP

cols = st.columns(len(top_types))
selected_types = []

for col, t in zip(cols, top_types):
    with col:
        if st.checkbox(t, value=True, key=f"chk_deaths_{selected_region}_{t}"):
            selected_types.append(t)

if len(selected_types) == 0:
    st.info("👆 최소 1개 이상의 재해 유형을 선택해야 그래프가 표시됩니다.")
    st.stop()

df_deaths = (
    df_region[df_region["Disaster Type"].isin(selected_types)]
    .groupby(["Start Year", "Disaster Type"])["Total Deaths"]
    .sum()
    .reset_index()
)

ordered_selected = [t for t in top_types if t in selected_types]
df_deaths["Disaster Type"] = pd.Categorical(
    df_deaths["Disaster Type"],
    categories=ordered_selected,
    ordered=True
)
df_deaths = df_deaths.sort_values(["Start Year", "Disaster Type"])

min_y = int(df_deaths["Start Year"].min())
max_y = int(df_deaths["Start Year"].max())
year_range = st.slider(
    "연도 범위 (사망자)",
    min_y,
    max_y,
    (min_y, max_y),
    key="year_range_deaths"
)

df_deaths = df_deaths[
    (df_deaths["Start Year"] >= year_range[0]) &
    (df_deaths["Start Year"] <= year_range[1])
]

fig_deaths = px.area(
    df_deaths,
    x="Start Year",
    y="Total Deaths",
    color="Disaster Type",
    template="plotly_dark",
    category_orders={"Disaster Type": ordered_selected},
    color_discrete_map=color_map,
    labels={
        "Start Year": "연도",
        "Total Deaths": "사망자 수",
        "Disaster Type": "유형"
    },
    title=f"{selected_region} — 시간에 따른 재해 사망자 추이"
)

fig_deaths.update_traces(opacity=0.7)

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

# 섹션 4 인사이트
st.info(
    "**💡 인사이트**\n\n"
    "재해 대응 능력, 보건 인프라, 도시 밀도에 따라 같은 재해도 다른 결과를 낳습니다.\n\n"
    "사망자 수는 자연현상보다 사회 시스템의 수준을 더 많이 반영합니다."
)

# -----------------------------------------------------------------------------
# Storytelling Interactive Visualization
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🧭 섹션 5. 각 대륙별로 어떤 재해가 가장 큰 영향을 미쳤을까?")

if "story_step" not in st.session_state:
    st.session_state["story_step"] = 0

def next_step():
    st.session_state["story_step"] += 1

def prev_step():
    st.session_state["story_step"] = max(0, st.session_state["story_step"] - 1)

def reset_story():
    for k in ["story_step", "story_region", "story_year_end", "story_metric_mode"]:
        if k in st.session_state:
            del st.session_state[k]

nav_l, nav_c, nav_r = st.columns([3, 5, 2])

with nav_l:
    if st.session_state["story_step"] > 0:
        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            st.button("⬅ 이전", on_click=prev_step)
        with col_b2:
            if 0 < st.session_state["story_step"] < 4:
                st.button("다음 ➜", on_click=next_step)

with nav_r:
    st.button("↩ 스토리 초기화", on_click=reset_story)

@st.cache_data(show_spinner=False)
def story_agg_no_window(df: pd.DataFrame, region: str, year_end: int):
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

if st.session_state["story_step"] == 0:
    st.info(
        "대륙별로 재해 발생/인명피해가 어떻게 달라졌는지를 탐색해보세요!\n\n"
        "➡️ 준비되면 **시작**을 눌러주세요."
    )
    st.button("🚀 시작", on_click=next_step)

if st.session_state["story_step"] == 1:
    st.markdown("### 먼저, 가장 궁금한 대륙을 선택해 주세요.")

    regions = ["Global"] + sorted(df_raw["Region"].dropna().unique().tolist())
    if "story_region" not in st.session_state:
        st.session_state["story_region"] = "Global"

    st.session_state["story_region"] = st.radio(
        "대륙 선택",
        regions,
        horizontal=True,
        index=regions.index(st.session_state["story_region"]) if st.session_state["story_region"] in regions else 0,
        key="story_region_selector"
    )

if st.session_state["story_step"] == 2:
    st.markdown("### 어떤 기간을 살펴볼까요?")
    st.caption("시작 연도는 1970년 고정이며, 마지막 연도만 선택합니다.")

    FIXED_START = 1970
    data_max_minus1 = int(df_raw["Start Year"].max()) - 1
    max_year = min(2025, data_max_minus1)

    if "story_year_end" not in st.session_state:
        st.session_state["story_year_end"] = max_year

    col1, col2 = st.columns([6, 4])

    with col1:
        st.session_state["story_year_end"] = st.slider(
            f"마지막 연도 (시작: {FIXED_START} 고정)",
            min_value=FIXED_START,
            max_value=max_year,
            value=st.session_state["story_year_end"],
            step=1
        )
        st.caption(f"선택 범위: **{FIXED_START}–{st.session_state['story_year_end']}**")

    with col2:
        if "story_metric_mode" not in st.session_state:
            st.session_state["story_metric_mode"] = "발생 건수"

        st.session_state["story_metric_mode"] = st.radio(
            "초점",
            ["발생 건수", "사망자 수"],
            horizontal=True,
            index=0 if st.session_state["story_metric_mode"] == "발생 건수" else 1,
            key="story_metric_selector"
        )

def make_bar_race_with_trail(
    df_yearly: pd.DataFrame,
    y_col: str,
    region: str,
    year_end: int,
    topN: int = 5,
    trail_years: int = 5,
):
    d = df_yearly[["Start Year", "Disaster Type", y_col]].copy()
    d = d[d["Start Year"] <= year_end]
    d = d[d[y_col].fillna(0) > 0]

    if d.empty:
        return None

    years = sorted(d["Start Year"].unique().tolist())

    q = 0.98 if y_col == "Deaths" else 0.95
    x_cap = float(d[y_col].quantile(q))
    x_cap = max(x_cap, 1.0)
    x_max = x_cap * 1.15

    def top_for_year(y: int):
        g = d[d["Start Year"] == y].sort_values(y_col, ascending=False).head(topN)
        order = g["Disaster Type"].tolist()
        vals_raw = g[y_col].astype(float).tolist()
        vals_plot = [min(v, x_cap) for v in vals_raw]
        return order, vals_plot, vals_raw

    pivot = d.pivot_table(index="Start Year", columns="Disaster Type", values=y_col, aggfunc="sum").fillna(0)

    first_year = years[0]
    order0, vals0_plot, vals0_raw = top_for_year(first_year)

    bar = go.Bar(
        x=vals0_plot,
        y=order0,
        orientation="h",
        marker=dict(color=[DISASTER_COLOR_MAP.get(t, "#888") for t in order0]),
        text=[f"{int(v):,}" for v in vals0_raw],
        textposition="inside",
        insidetextanchor="end",
        cliponaxis=False,
        hovertemplate="%{y}<br>%{customdata:,}<extra></extra>",
        customdata=vals0_raw,
        name="",
    )

    trail_traces = []
    for k in range(1, trail_years + 1):
        alpha = max(0.08, 0.35 * (1 - (k / (trail_years + 1))))
        trail_traces.append(
            go.Scatter(
                x=[pivot.loc[first_year - k, t] if (first_year - k) in pivot.index and t in pivot.columns else None for t in order0],
                y=order0,
                mode="markers",
                marker=dict(
                    size=8,
                    opacity=alpha,
                    color=[DISASTER_COLOR_MAP.get(t, "#888") for t in order0],
                    symbol="circle",
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    frames = []
    for y in years:
        order, vals_plot, vals_raw = top_for_year(y)
        bar_y = order
        bar_x = vals_plot

        trails = []
        for k in range(1, trail_years + 1):
            alpha = max(0.08, 0.35 * (1 - (k / (trail_years + 1))))
            prev_y = y - k
            trails.append(
                go.Scatter(
                    x=[pivot.loc[prev_y, t] if (prev_y in pivot.index and t in pivot.columns) else None for t in order],
                    y=order,
                    mode="markers",
                    marker=dict(
                        size=8,
                        opacity=alpha,
                        color=[DISASTER_COLOR_MAP.get(t, "#888") for t in order],
                        symbol="circle",
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        frames.append(
            go.Frame(
                name=str(y),
                data=[
                    go.Bar(
                        x=bar_x,
                        y=bar_y,
                        orientation="h",
                        marker=dict(color=[DISASTER_COLOR_MAP.get(t, "#888") for t in bar_y]),
                        text=[f"{int(v):,}" for v in vals_raw],
                        textposition="outside",
                        cliponaxis=False,
                        customdata=vals_raw,
                        hovertemplate="%{y}<br>%{customdata:,}<extra></extra>",
                    ),
                    *trails
                ],
                layout=go.Layout(
                    yaxis=dict(categoryorder="array", categoryarray=bar_y),
                    title=dict(text=f"연도별 Top {topN} ({'발생 건수' if y_col=='Occurrences' else '사망자 수'}) — {region} (1970–{year_end})<br><sup>{y}</sup>")
                )
            )
        )

    fig = go.Figure(data=[bar, *trail_traces], frames=frames)

    fig.update_layout(
        template="plotly_dark",
        height=560,
        margin=dict(l=260, r=60, t=90, b=110),
        xaxis=dict(title=("발생 건수" if y_col == "Occurrences" else "사망자 수"), range=[0, x_max], fixedrange=False),
        yaxis=dict(title="", categoryorder="array", categoryarray=order0, autorange="reversed", automargin=False),
        showlegend=False,
        title=dict(text=f"연도별 Top {topN} ({'발생 건수' if y_col=='Occurrences' else '사망자 수'}) — {region} (1970–{year_end})<br><sup>{first_year}</sup>", x=0.02),
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                x=0.02,
                y=-0.12,
                buttons=[
                    dict(
                        label="▶ 재생",
                        method="animate",
                        args=[
                            None,
                            dict(
                                frame=dict(duration=600, redraw=True),
                                transition=dict(duration=450, easing="cubic-in-out"),
                                fromcurrent=True
                            )
                        ],
                    ),
                    dict(
                        label="⏸ 일시정지",
                        method="animate",
                        args=[
                            [None],
                            dict(frame=dict(duration=0, redraw=False), mode="immediate"),
                        ],
                    ),
                ],
            )
        ],
        sliders=[
            dict(
                x=0.15,
                y=-0.12,
                len=0.82,
                active=0,
                currentvalue=dict(prefix="연도 = "),
                pad=dict(t=10),
                steps=[
                    dict(
                        method="animate",
                        args=[
                            [str(y)],
                            dict(
                                frame=dict(duration=0, redraw=True),
                                transition=dict(duration=350, easing="cubic-in-out"),
                                mode="immediate",
                            ),
                        ],
                        label=str(y),
                    )
                    for y in years
                ],
            )
        ],
        autosize=False,
        uirevision="bar_race_lock",
    )

    return fig

# 대륙별 인사이트 정의
REGION_INSIGHTS = {
    "Global": """
**🌍 전 지구적 변화**

기후 변화는 더 이상 특정 지역의 문제가 아닙니다.

전 지구적 현상으로서, 재해의 '종류' 자체를 변화시키고 있습니다.

1. 재해는 자연이 아니라 구조의 문제이며, 피해 규모는 지형보다 도시/보건/인프라에 더 크게 좌우됩니다.

2. 재해의 '종류'는 홍수·폭풍 중심에서 열·가뭄·산불로 변화하고 있으며, 이는 기후 변화의 결과임을 암시합니다.

""",
    "Asia": """
**🌏 아시아 — 거대 인구와 극한 기상의 격전지**

* **특징**: 홍수·폭풍이 절대적 비중

* **지형/사회**: 몬순 + 대규모 하천 + 고인구 밀도

* **최근 상황**:

   * 급격한 도시화 + 인구 밀집으로 인해 전염병이 상위권에 빈번히 등장

""",
    "Africa": """
**🌍 아프리카 — 가뭄과 전염병, 보건 인프라의 취약성**

* **특징**: 전염병 비중이 매우 높음

* **배경**: 취약한 보건·위생 시스템

* **최근 상황**:

   * 기후 변화로 인한 극단적 강수 패턴으로 홍수 급증
""",
    "Europe": """
**🇪🇺 유럽 — 기후 변화가 만든 새로운 재난**

* **특징**: 이상 기온·산불 증가

* **배경**: 온화한 기후에 최적화된 인프라

* **최근**: 지중해 연안 산불의 상시화
""",
    "Americas": """
**🌎 아메리카 — 자연재해와 인적 재난의 공존**

* **특징**: 폭풍 + 교통·산업 사고

* **배경**: 허리케인 경로 + 대규모 물류망

* **최근**: 서부·아마존 지역 산불·가뭄 심화
""",
    "Oceania": """
**🌊 오세아니아 — 해양성 기후와 고립된 생태계**

* **특징**: 사이클론·산불

* **배경**: 섬 국가 + 건조한 대륙 기후

* **위험**: 해수면 상승과 복합 재난
"""
}

if st.session_state["story_step"] == 3:
    region = st.session_state.get("story_region", "Global")
    year_end = st.session_state.get(
        "story_year_end",
        int(df_raw["Start Year"].max()) - 1
    )

    focus = st.session_state.get("story_metric_mode", "발생 건수")

    df_sum, df_yearly = story_agg_no_window(df_raw, region, year_end)

    if df_sum.empty:
        st.warning("선택한 조건에서 표시할 데이터가 없습니다.")
        st.stop()

    if focus == "발생 건수":
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

    st.markdown("### 어떤 재해가 가장 큰 영향을 미쳤는지 확인해보세요!")
    st.success(
        f"**{region}**에서 **1970–{year_end}** 동안\n\n"
        f"➡️ **{top_type}**의 **{metric_title}**가 가장 큽니다.\n\n"
        f"- 합계: **{top_val:,}**"
    )

    topN = 5
    y_col = "Occurrences" if focus == "발생 건수" else "Deaths"

    fig_top_anim = make_bar_race_with_trail(
        df_yearly=df_yearly,
        y_col=y_col,
        region=region,
        year_end=year_end,
        topN=5,
        trail_years=6,
    )

    if fig_top_anim is None:
        st.warning("선택한 조건에서 표시할 데이터가 없습니다.")
        st.stop()

    st.plotly_chart(fig_top_anim, use_container_width=True)

    # 대륙별 인사이트 표시
    insight_text = REGION_INSIGHTS.get(region, "")
    if insight_text:
        st.info(f"**💡 대륙별 인사이트**\n\n{insight_text}")
    
    st.info("➡️ 다음 단계에서 특정 재해를 골라 더 자세히 볼 수 있어요.")

if st.session_state["story_step"] == 4:
    st.markdown("### 이제 특정 재해를 골라 더 자세히 확인해 볼까요?")

    region = st.session_state.get("story_region", "Global")

    cand = sorted(df_raw["Disaster Type"].dropna().unique().tolist())
    choice = st.selectbox("재해 유형 선택", cand)

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

    MINY = 1970
    MAXY = int(df_raw["Start Year"].max()) - 1
    d = d[(d["Start Year"] >= MINY) & (d["Start Year"] <= MAXY)]

    def make_anim(d):
        years = d["Start Year"].tolist()
        fig = go.Figure()

        d0 = d[d["Start Year"] <= years[0]]

        fig.add_bar(
            x=d0["Start Year"],
            y=d0["Occurrences"],
            name="발생 건수",
            marker=dict(color=DISASTER_COLOR_MAP.get(choice, "#1f77b4")),
            opacity=0.70,
            yaxis="y"
        )

        fig.add_scatter(
            x=d0["Start Year"],
            y=d0["Deaths"],
            name="사망자 수",
            mode="lines+markers",
            line=dict(color=DISASTER_COLOR_MAP.get(choice, "#1f77b4"), width=3),
            yaxis="y2"
        )

        frames = []
        for y in years:
            dy = d[d["Start Year"] <= y]
            frames.append(
                go.Frame(
                    name=str(y),
                    data=[
                        go.Bar(x=dy["Start Year"], y=dy["Occurrences"], opacity=0.70),
                        go.Scatter(x=dy["Start Year"], y=dy["Deaths"])
                    ]
                )
            )

        fig.frames = frames

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
                            label="▶ 재생",
                            method="animate",
                            args=[None, dict(frame=dict(duration=80, redraw=True))]
                        )
                    ]
                )
            ],
            yaxis=dict(title="발생 건수"),
            yaxis2=dict(title="사망자 수", overlaying="y", side="right"),
            autosize=False,
            margin=dict(l=220, r=40, t=90, b=60),
        )
        fig.update_yaxes(automargin=False)

        return fig

    fig_anim = make_anim(d)
    st.plotly_chart(fig_anim, use_container_width=True)

    st.success("✅ 다른 대륙도 자유롭게 탐색해 보세요!")

# -----------------------------------------------------------------------------
# 4. KOREA SECTION
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; margin-top: 6px; margin-bottom: 6px;">
        <div style="font-size: 3.4rem; font-weight: 900; line-height: 1.05;color: #ff3b3b;">
            🇰🇷 한국 재해 심층 분석
        </div>
        <div style="font-size: 1.35rem; font-weight: 600; opacity: 0.85; margin-top: 8px;">
            한국의 재해는 어떻게 변해왔는가?
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

START_Y = 1970

def normalize_korea_df(df_korea_raw: pd.DataFrame) -> pd.DataFrame:
    dfk = df_korea_raw.copy()

    if "Year" in dfk.columns:
        year_col = "Year"
    elif "Start Year" in dfk.columns:
        year_col = "Start Year"
    else:
        raise ValueError(f"[KOREA] Year 컬럼을 찾을 수 없어요. 현재 컬럼: {list(dfk.columns)}")

    if "Total_Deaths" in dfk.columns:
        deaths_col = "Total_Deaths"
    elif "Total Deaths" in dfk.columns:
        deaths_col = "Total Deaths"
    else:
        raise ValueError(f"[KOREA] Deaths 컬럼을 찾을 수 없어요. 현재 컬럼: {list(dfk.columns)}")

    if "Disaster Type" in dfk.columns:
        type_col = "Disaster Type"
    else:
        raise ValueError(f"[KOREA] 'Disaster Type' 컬럼이 없어요. 현재 컬럼: {list(dfk.columns)}")

    dfk = dfk.rename(columns={year_col: "Year", deaths_col: "Total_Deaths", type_col: "Disaster Type"})

    dfk["Year"] = pd.to_numeric(dfk["Year"], errors="coerce").astype("Int64")
    dfk["Total_Deaths"] = pd.to_numeric(dfk["Total_Deaths"], errors="coerce").fillna(0)
    dfk["Disaster Type"] = dfk["Disaster Type"].astype(str)

    dfk = dfk.dropna(subset=["Year"])
    dfk["Year"] = dfk["Year"].astype(int)

    dfk = dfk.groupby(["Year", "Disaster Type"], as_index=False)["Total_Deaths"].sum()

    return dfk

def make_korea_panel(dfk_norm: pd.DataFrame, start_year: int = 1970, top_n: int = 5):
    dfk = dfk_norm[dfk_norm["Year"] >= start_year].copy()
    if dfk.empty:
        return [], dfk

    end_year = int(dfk["Year"].max())

    top_types = (
        dfk.groupby("Disaster Type")["Total_Deaths"]
        .sum()
        .nlargest(top_n)
        .index
        .tolist()
    )

    years = pd.DataFrame({"Year": list(range(start_year, end_year + 1))})
    base = years.merge(pd.DataFrame({"Disaster Type": top_types}), how="cross")

    panel = (
        base.merge(dfk[dfk["Disaster Type"].isin(top_types)], on=["Year", "Disaster Type"], how="left")
            .fillna({"Total_Deaths": 0})
            .sort_values(["Year", "Disaster Type"])
    )

    return top_types, panel

try:
    dfk_norm = normalize_korea_df(df_korea_raw)
    top_5_kor, df_kor_filtered = make_korea_panel(dfk_norm, start_year=START_Y, top_n=5)
except Exception as e:
    st.error(f"한국 데이터 처리 중 오류: {e}")
    st.stop()

if len(top_5_kor) == 0 or df_kor_filtered.empty:
    st.warning("한국 데이터가 비어있어서 표시할 수 없습니다.")
    st.stop()

st.subheader("📈 연도별 재해 발생 수 추이")
st.markdown("##### 재난의 종류가 바뀌고 있다?!")

fig_bar = px.bar(
    df_kor_filtered,
    x="Year",
    y="Total_Deaths",
    color="Disaster Type",
    template="plotly_dark",
    category_orders={"Disaster Type": top_5_kor},
    color_discrete_map=DISASTER_COLOR_MAP,
    opacity=0.7
)
fig_bar.update_layout(
    xaxis_title="연도",
    yaxis_title="사망자 수",
    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
    height=420,
    bargap=0.2
)
st.plotly_chart(fig_bar, use_container_width=True)

# 한국 섹션 1 인사이트
st.info(
    "**💡 인사이트**\n\n"
    "과거에는 태풍과 홍수가 주요 재난 유형으로 두드러졌으나 최근으로 갈수록 기후 관련 재난의 발생 빈도가 증가하는 경향이 관찰됩니다.\n\n"
    "이는 재난이 단발성 이벤트가 아니라, 매년 반복되는 구조적 위험으로 변화하고 있음을 시사합니다."
)

st.markdown("<br><br>", unsafe_allow_html=True)

st.subheader("🧍 연도별 재해 사망자 추이 및 규모")
st.markdown("##### 대규모 인명 피해는 감소했지만, 위험은 사라지지 않았다!")

col_ctrl1, col_ctrl2 = st.columns([2.2, 1])

with col_ctrl1:
    max_year_kor = int(df_kor_filtered["Year"].max())
    kor_year = st.slider(
        "연도 선택",
        START_Y,
        max_year_kor,
        min(2003, max_year_kor)
    )

with col_ctrl2:
    default_type = "Fire (Miscellaneous)"
    default_index = top_5_kor.index(default_type) if default_type in top_5_kor else 0

    kor_type = st.selectbox(
        "재해 유형 선택",
        top_5_kor,
        index=default_index,
        key="kor_type_pic"
    )

subset = df_kor_filtered[
    (df_kor_filtered["Year"] == kor_year) &
    (df_kor_filtered["Disaster Type"] == kor_type)
]
death_count = int(subset["Total_Deaths"].sum()) if not subset.empty else 0

current_context = f"{kor_year}_{kor_type}"

if "pictogram_context" not in st.session_state:
    st.session_state.pictogram_context = current_context

if st.session_state.pictogram_context != current_context:
    st.session_state.pictogram_context = current_context
    st.session_state.pictogram_step = 0
    st.session_state.pictogram_active = False

if "pictogram_step" not in st.session_state:
    st.session_state.pictogram_step = 0

if "pictogram_active" not in st.session_state:
    st.session_state.pictogram_active = False

col_pic_left, col_pic_right = st.columns([1, 3])

with col_pic_left:
    st.markdown("<div style='text-align:center; margin-top:40px;'>", unsafe_allow_html=True)
    st.markdown(f"<h2>{death_count:,} 명 사망</h2>", unsafe_allow_html=True)

    speed = st.slider(
        "애니메이션 속도",
        0.005,
        0.05,
        0.015,
        step=0.005,
        key="pic_speed"
    )

    cA, cB = st.columns(2)
    with cA:
        play = st.button("▶ 재생", key="pic_play")
    with cB:
        reset = st.button("↩ 초기화", key="pic_reset")

    st.markdown("</div>", unsafe_allow_html=True)
    st.info("1 블록 = 1명")

with col_pic_right:
    UNIT_PER_ICON = 1
    base_icons = 430
    active_icons = math.ceil(death_count / UNIT_PER_ICON)

    total_icons = max(base_icons, active_icons)

    if death_count == 0:
        active_class = ""
    elif death_count > 100:
        active_class = "active-red"
    elif death_count > 50:
        active_class = "active-orange"
    else:
        active_class = "active-yellow"

    holder = st.empty()

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

    render(st.session_state.pictogram_step)

    if reset:
        st.session_state.pictogram_step = 0
        st.session_state.pictogram_active = False
        render(0)
        st.stop()

    if play:
        st.session_state.pictogram_active = True
        st.session_state.pictogram_step = 0

        for step in range(0, active_icons + 1):
            st.session_state.pictogram_step = step
            render(step)
            time.sleep(speed)

# 한국 섹션 2 인사이트
st.info(
    "**💡 인사이트**\n\n"
    "대한민국은 대형 참사를 유발하는 재난의 빈도는 줄였지만, 기후 조건과 사회적 취약 계층의 노출에 따라 특정 재해가 발생할 경우\n\n"
    "사회적 충격이 크게 증폭되는 구조를 보이며, 이는 고밀도 도시 구조와 연관되어 있습니다."
)

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: grey; font-size: 0.8rem;'>"
    "데이터 출처: EM-DAT, 한국 재난 통계</p>",
    unsafe_allow_html=True
)
