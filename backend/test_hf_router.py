"""
HuggingFaceルーター動作確認
"""
from app.agents.hf_router import route_with_hf_scored

tests = [
    # 曖昧な表現（Step3でHFが判断）
    "スタッフの定着率が下がっている",
    "レセプト請求の確認をしたい",
    "現場の安全管理について教えて",
    "誰に任せればいいか",
    "来月の資金が心配",
    # 業種別テスト
    "介護スタッフの夜勤シフトを最適化したい",
    "工場の設備点検記録を管理したい",
    "建設現場の安全教育をどうすればいいか",
    "エンジニアのスキルマップを作りたい",
    "病院のコスト削減方法を教えて",
]

print("=" * 60)
print("HuggingFace ルーター動作確認")
print("=" * 60)

for q in tests:
    r = route_with_hf_scored(q)
    print(f"Q: {q}")
    print(f"→ route={r['route']} score={r['score']}")
    print()