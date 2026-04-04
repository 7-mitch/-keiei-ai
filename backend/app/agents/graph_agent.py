"""
graph_agent.py — データグラフ生成エージェント（Plotly + scikit-learn予測）
グラフ種類を自動判定・将来予測付き
"""
import base64
import pandas as pd
import numpy as np


def detect_graph_type(df: pd.DataFrame) -> str:
    """データの特性からグラフ種類を自動判定"""
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    rows         = len(df)

    has_date = any(
        "date" in c.lower() or "日付" in c or "年月" in c or "month" in c.lower()
        for c in df.columns
    )

    if has_date and len(numeric_cols) >= 1:
        return "timeseries"
    if rows <= 10 and len(numeric_cols) == 1:
        return "bar"
    if rows <= 20 and len(numeric_cols) >= 2:
        return "heatmap"
    if len(numeric_cols) >= 2 and rows >= 20:
        return "scatter"
    if rows > 15:
        return "line"
    return "bar"


def predict_trend(series: pd.Series, periods: int = 3):
    """線形回帰で将来予測（scikit-learn）"""
    try:
        from sklearn.linear_model import LinearRegression

        y = series.dropna().values
        if len(y) < 3:
            return None, None

        X        = np.arange(len(y)).reshape(-1, 1)
        model    = LinearRegression()
        model.fit(X, y)

        future_X = np.arange(len(y), len(y) + periods).reshape(-1, 1)
        future_y = model.predict(future_X)
        r2       = model.score(X, y)

        return future_y, round(r2, 3)

    except Exception as e:
        print(f"[GRAPH] 予測エラー: {e}")
        return None, None


def generate_graph(df: pd.DataFrame, filename: str) -> str | None:
    """メイン関数：Plotlyでグラフ生成"""
    try:
        return _generate_plotly(df, filename)
    except Exception as e:
        print(f"[GRAPH] Plotlyエラー → フォールバック: {e}")
        return _generate_matplotlib_fallback(df, filename)


def _generate_plotly(df: pd.DataFrame, filename: str) -> str | None:
    """Plotlyでインタラクティブグラフを生成しPNG変換"""
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return None

    label_col  = df.columns[0]
    graph_type = detect_graph_type(df)
    col_count  = min(len(numeric_cols), 3)
    colors     = ["#3B82F6", "#10B981", "#F59E0B"]

    # ===== 時系列（予測付き折れ線）=====
    if graph_type == "timeseries":
        fig = make_subplots(
            rows=col_count, cols=1,
            subplot_titles=numeric_cols[:3],
            vertical_spacing=0.1,
        )
        for idx, col in enumerate(numeric_cols[:3], 1):
            series = df[col]
            x_vals = df[label_col].astype(str).tolist()

            fig.add_trace(go.Scatter(
                x=x_vals, y=series,
                mode="lines+markers",
                name=col,
                line=dict(width=2, color=colors[idx - 1]),
                marker=dict(size=6),
            ), row=idx, col=1)

            future_y, r2 = predict_trend(series, periods=3)
            if future_y is not None:
                fig.add_trace(go.Scatter(
                    x=[f"予測{i+1}" for i in range(3)],
                    y=future_y,
                    mode="lines+markers",
                    name=f"{col} 予測（R²={r2}）",
                    line=dict(dash="dot", width=2, color="orange"),
                    marker=dict(size=6, symbol="diamond"),
                ), row=idx, col=1)

        fig.update_layout(
            title=dict(text=f"{filename}（時系列分析・予測付き）", font=dict(size=14)),
            height=320 * col_count,
            hovermode="x unified",
            template="plotly_white",
        )

    # ===== ヒートマップ（相関行列）=====
    elif graph_type == "heatmap":
        corr = df[numeric_cols].corr()
        fig  = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            colorscale="RdBu",
            zmid=0,
            text=corr.round(2).values,
            texttemplate="%{text}",
            textfont=dict(size=10),
        ))
        fig.update_layout(
            title=dict(text=f"{filename}（相関ヒートマップ）", font=dict(size=14)),
            height=500,
            template="plotly_white",
        )

    # ===== 散布図 =====
    elif graph_type == "scatter" and len(numeric_cols) >= 2:
        fig = px.scatter(
            df,
            x=numeric_cols[0],
            y=numeric_cols[1],
            color=label_col if df[label_col].dtype == object else None,
            size=numeric_cols[2] if len(numeric_cols) > 2 else None,
            title=f"{filename}（散布図）",
            hover_data=df.columns.tolist(),
            template="plotly_white",
        )
        fig.update_layout(height=500)

    # ===== 棒グラフ（デフォルト・予測付き）=====
    else:
        fig = make_subplots(
            rows=1, cols=col_count,
            subplot_titles=numeric_cols[:3],
        )
        for idx, col in enumerate(numeric_cols[:3], 1):
            series = df[col]

            fig.add_trace(go.Bar(
                x=df[label_col].astype(str),
                y=series,
                name=col,
                marker_color=colors[idx - 1],
                text=series.apply(lambda v: f"{v:,.0f}"),
                textposition="outside",
            ), row=1, col=idx)

            future_y, r2 = predict_trend(series, periods=3)
            if future_y is not None:
                fig.add_trace(go.Bar(
                    x=[f"予測{i+1}" for i in range(3)],
                    y=future_y,
                    name=f"{col} 予測（R²={r2}）",
                    marker_color="orange",
                    opacity=0.6,
                ), row=1, col=idx)

        fig.update_layout(
            title=dict(text=f"{filename}（予測付き）", font=dict(size=14)),
            height=450,
            bargap=0.15,
            template="plotly_white",
        )

    # PNG変換してbase64で返す
    img_bytes = fig.to_image(
        format="png",
        width=1200,
        height=fig.layout.height or 500,
        scale=1.5,
    )
    return base64.b64encode(img_bytes).decode()


def _generate_matplotlib_fallback(df: pd.DataFrame, filename: str) -> str | None:
    """フォールバック用matplotlibグラフ（Plotlyが失敗した場合のみ）"""
    try:
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import japanize_matplotlib

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            return None

        col_count = min(len(numeric_cols), 3)
        fig, axes = plt.subplots(1, col_count, figsize=(5 * col_count, 4))
        if col_count == 1:
            axes = [axes]

        label_col = df.columns[0]

        for ax, col in zip(axes, numeric_cols[:3]):
            if len(df) <= 15:
                ax.bar(
                    df[label_col].astype(str), df[col],
                    color="steelblue", edgecolor="white",
                )
                ax.set_xticklabels(
                    df[label_col].astype(str),
                    rotation=45, ha="right", fontsize=8,
                )
            else:
                ax.plot(df[col], marker="o", color="steelblue", linewidth=1.5)
                ax.set_xlabel("行番号")

            ax.set_title(col, fontsize=10)
            ax.set_ylabel(col, fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
            )

        fig.suptitle(filename, fontsize=11)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    except Exception as e:
        print(f"[GRAPH] matplotlibフォールバックエラー: {e}")
        return None