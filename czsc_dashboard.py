"""
CZSC 量化分析仪表板

用法：uv run streamlit run czsc_dashboard.py
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="CZSC 量化分析仪表板", layout="wide", page_icon="📈")

import czsc
from czsc.core import CZSC, BarGenerator, Freq, format_standard_kline
from czsc.mock import generate_symbol_kines
from czsc.svc import show_weight_backtest
from czsc.utils.plotting.kline import plot_czsc_chart

FREQ_MAP = {"30分钟": Freq.F30, "15分钟": Freq.F15, "5分钟": Freq.F5, "日线": Freq.D}

# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------
st.sidebar.title("CZSC 量化分析")
page = st.sidebar.radio("功能模块", ["缠论K线分析", "策略回测分析", "多频率联立"])

# ---------------------------------------------------------------------------
# 页面 1：缠论 K 线分析
# ---------------------------------------------------------------------------
if page == "缠论K线分析":
    st.title("缠论 K 线分析")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        symbol = st.text_input("品种代码", value="000001")
    with col2:
        freq = st.selectbox("K线频率", ["30分钟", "15分钟", "5分钟", "日线"], index=0)
    with col3:
        sdt = st.date_input("开始日期", value=pd.Timestamp("2024-01-01"))
    with col4:
        edt = st.date_input("结束日期", value=pd.Timestamp("2024-06-01"))

    if st.button("开始分析", type="primary", use_container_width=True):
        with st.spinner("正在生成K线数据并进行缠论分析..."):
            df = generate_symbol_kines(symbol, freq, sdt=sdt.strftime("%Y%m%d"), edt=edt.strftime("%Y%m%d"))
            bars = format_standard_kline(df, freq=FREQ_MAP[freq])
            c = CZSC(bars)

        # 统计指标
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("K线数量", len(c.bars_raw))
        c2.metric("分型数量", len(c.fx_list))
        c3.metric("笔数量", len(c.bi_list))
        c4.metric("最新价", f"{c.bars_raw[-1].close:.2f}")

        # Plotly 交互式 K 线图（支持缩放、拖拽、十字光标）
        chart = plot_czsc_chart(c, height=700)
        st.plotly_chart(chart.fig, use_container_width=True, config={"scrollZoom": True})

        # 笔列表
        if c.bi_list:
            with st.expander("笔列表详情", expanded=False):
                bi_records = []
                for bi in c.bi_list:
                    bi_records.append({
                        "方向": bi.direction.value,
                        "起始时间": bi.sdt,
                        "结束时间": bi.edt,
                        "最高价": f"{bi.high:.2f}",
                        "最低价": f"{bi.low:.2f}",
                        "变动幅度": f"{abs(bi.high - bi.low) / bi.low * 100:.2f}%",
                    })
                st.dataframe(pd.DataFrame(bi_records), use_container_width=True)

# ---------------------------------------------------------------------------
# 页面 2：策略回测分析
# ---------------------------------------------------------------------------
elif page == "策略回测分析":
    st.title("策略回测分析")

    col1, col2, col3 = st.columns(3)
    with col1:
        fee = st.number_input("单边手续费 (BP)", value=2, min_value=0, max_value=50)
    with col2:
        digits = st.number_input("权重小数位数", value=2, min_value=1, max_value=4)
    with col3:
        seed = st.number_input("随机种子", value=42, min_value=0, max_value=9999)

    if st.button("运行回测", type="primary", use_container_width=True):
        with st.spinner("正在生成模拟数据并执行回测..."):
            dfw = czsc.mock.generate_klines_with_weights(seed=seed)

        st.success(f"数据就绪：{len(dfw)} 条记录，{dfw['symbol'].nunique()} 个品种，"
                   f"时间 {dfw['dt'].min().strftime('%Y-%m-%d')} ~ {dfw['dt'].max().strftime('%Y-%m-%d')}")

        show_weight_backtest(
            dfw, fee=fee, digits=digits,
            show_drawdowns=True,
            show_splited_daily=True,
            show_yearly_stats=True,
            show_monthly_return=True,
        )

# ---------------------------------------------------------------------------
# 页面 3：多频率联立分析
# ---------------------------------------------------------------------------
elif page == "多频率联立":
    st.title("多频率 K 线联立分析")

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("品种代码", value="600000", key="mf_symbol")
    with col2:
        sdt = st.date_input("开始日期", value=pd.Timestamp("2024-01-01"), key="mf_sdt")
    with col3:
        edt = st.date_input("结束日期", value=pd.Timestamp("2024-06-01"), key="mf_edt")

    target_freqs = st.multiselect("合成目标频率", ["日线", "周线"], default=["日线"])

    if st.button("开始联立分析", type="primary", use_container_width=True):
        with st.spinner("正在进行多频率分析..."):
            df = generate_symbol_kines(symbol, "30分钟",
                                       sdt=sdt.strftime("%Y%m%d"),
                                       edt=edt.strftime("%Y%m%d"))
            bars = format_standard_kline(df, freq=Freq.F30)

            bg = BarGenerator("30分钟", target_freqs, max_count=5000)
            for bar in bars:
                bg.update(bar)

        # Tab 展示各频率
        all_freqs = ["30分钟"] + target_freqs
        tabs = st.tabs(all_freqs)

        with tabs[0]:
            c = CZSC(bars)
            m1, m2 = st.columns(2)
            m1.metric("K线数", len(c.bars_raw))
            m2.metric("笔数", len(c.bi_list))

            chart = plot_czsc_chart(c, height=600)
            st.plotly_chart(chart.fig, use_container_width=True, config={"scrollZoom": True})

        for i, tf in enumerate(target_freqs):
            with tabs[i + 1]:
                tf_bars = bg.bars.get(tf, [])
                if not tf_bars:
                    st.warning(f"未能合成 {tf} K线")
                    continue

                c_tf = CZSC(tf_bars)
                m1, m2 = st.columns(2)
                m1.metric("K线数", len(c_tf.bars_raw))
                m2.metric("笔数", len(c_tf.bi_list))

                chart = plot_czsc_chart(c_tf, height=600)
                st.plotly_chart(chart.fig, use_container_width=True, config={"scrollZoom": True})
