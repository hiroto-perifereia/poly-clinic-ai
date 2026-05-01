import streamlit as st
from groq import Groq
from notion_client import Client
import json

# --- 1. ページ基本設定 ---
st.set_page_config(
    page_title="Medical AI Assistant",
    page_icon="🩺",
    layout="centered"
)

# --- 2. クライアント初期化 (直接記述) ---
# --- 2. クライアント初期化 (Secrets読み込み式に書き換え) ---
# ※直接書き込んでいたキーは削除します
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID = st.secrets["DATABASE_ID"]

groq_client = Groq(api_key=GROQ_API_KEY)
notion = Client(auth=NOTION_TOKEN)

# --- 3. セッション状態の初期化 ---
if "text_key" not in st.session_state:
    st.session_state.text_key = 0
if "res_json" not in st.session_state:
    st.session_state.res_json = None
if "saved" not in st.session_state:
    st.session_state.saved = False

# --- 4. ダイアログ機能 (削除確認用) ---
@st.dialog("入力内容の削除")
def reset_confirmation():
    st.warning("Notionに保存していない解析結果は消えてしまいますが、よろしいですか？")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("はい", use_container_width=True, type="primary"):
            st.session_state.res_json = None
            st.session_state.saved = False # 状態リセット
            st.session_state.text_key += 1 
            st.rerun()
    with c2:
        if st.button("いいえ", use_container_width=True):
            st.rerun()

# --- 5. サイドバー ---
with st.sidebar:
    st.title("🏥 設定・ガイド")
    output_length = st.radio(
        "出力のボリュームを選択",
        options=["簡潔に", "標準的", "詳しく"],
        index=1,
        horizontal=True
    )
    st.divider()
    st.info(f"現在のモード: **{output_length}**")
    st.caption("Developed by Hiroto Fujii")

# --- 6. メイン画面レイアウト ---
st.title("🩺 Poly-Clinic Support AI")
st.caption("実習の記憶を、CBTの知識とレポートへ。")

# 入力エリア
user_input = st.text_area(
    "実習中の気づきやメモを入力...", 
    placeholder="（例）70代男性、労作時呼吸困難...",
    height=180,
    key=f"input_area_{st.session_state.text_key}"
)

# 上部ボタン配置
col_top1, col_top2 = st.columns(2)
with col_top1:
    analyze_btn = st.button("解析を実行", use_container_width=True, type="primary")
with col_top2:
    if st.button("メモを削除", use_container_width=True):
        # 「解析結果がある」かつ「まだ保存していない」時だけダイアログを出す
        if st.session_state.res_json and not st.session_state.saved:
            reset_confirmation()
        else:
            # 解析前、あるいは保存済みの場合は無言で削除
            st.session_state.res_json = None
            st.session_state.saved = False
            st.session_state.text_key += 1
            st.rerun()

# --- 7. 解析ロジック ---
if analyze_btn:
    if not user_input:
        st.warning("メモを入力してください。")
    else:
        with st.spinner(f"「{output_length}」解析中..."):
            try:
                length_instruction = {
                    "簡潔に": "要点のみを数行で、極めて簡潔にまとめてください。",
                    "標準的": "重要事項を網羅しつつ、適切な長さでまとめてください。",
                    "詳しく": "背景知識や詳細なメカニズム、レポートにそのまま使えるレベルの深い考察まで、詳細に出力してください。"
                }[output_length]

                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system", 
                            "content": (
                                f"あなたは医学エキスパートです。入力されたメモから、診断のヒント、CBT/国試に出る重要知識、レポート用の考察を日本語の json 形式で出力してください。"
                                f"【出力の長さ】{length_instruction}"
                                "【重要制約】各項目は必ず単一の文字列(string)として出力し、リスト形式( [ ] )は絶対に使わないでください。箇条書きが必要な場合は、文字列内で改行(\\n)を使用してください。"
                                "項目: topic, cbt_knowledge, report_draft"
                            )
                        },
                        {"role": "user", "content": user_input}
                    ],
                    response_format={"type": "json_object"}
                )
                st.session_state.res_json = json.loads(response.choices[0].message.content)
                st.session_state.saved = False # 解析した直後は未保存状態
                st.rerun() 
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- 8. 結果表示 & 保存エリア ---
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.markdown(f"### 📌 テーマ: **{data['topic']}**")
    
    tab1, tab2 = st.tabs(["📚 CBT / 国試知識", "📝 レポート考察案"])
    with tab1:
        st.info(data['cbt_knowledge'])
    with tab2:
        st.success(data['report_draft'])

    st.write("") 
    if st.button("Notionに保存する", use_container_width=True):
        with st.spinner("Notionに同期中..."):
            try:
                cbt_val = data['cbt_knowledge']
                if isinstance(cbt_val, list):
                    cbt_val = "\n".join(map(str, cbt_val))
                
                report_val = data['report_draft']
                if isinstance(report_val, list):
                    report_val = "\n".join(map(str, report_val))

                notion.pages.create(
                    parent={"database_id": DATABASE_ID},
                    properties={
                        "Name": {"title": [{"text": {"content": str(data['topic'])}}]},
                        "CBT知識": {"rich_text": [{"text": {"content": cbt_val}}]},
                        "レポート考察": {"rich_text": [{"text": {"content": report_val}}]}
                    }
                )
                st.session_state.saved = True # 保存成功！
                st.success("✅ Notionに保存できました！リセットして次のメモに進めます。")
            except Exception as e:
                st.error(f"Notion保存エラー: {e}")