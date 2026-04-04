"""
graph_agent.py — データグラフ生成エージェント
"""
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # GUIなしで動作
import matplotlib.pyplot as plt
import japanize_matplotlib  # 日本語フォント対応


def generate_graph(df: pd.DataFrame, filename: str) -> str | None:
    """
    DataFrameからグラフを生成しbase64文字列で返す
    数値カラムがない場合はNoneを返す
    """
    try:
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
                # 少ない行数は棒グラフ
                ax.bar(
                    df[label_col].astype(str),
                    df[col],
                    color="steelblue",
                    edgecolor="white",
                )
                ax.set_xticklabels(
                    df[label_col].astype(str),
                    rotation=45,
                    ha="right",
                    fontsize=8,
                )
            else:
                # 多い行数は折れ線グラフ
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
        print(f"[GRAPH] グラフ生成エラー: {e}")
        return None