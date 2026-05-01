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

# --- 2. クライアント初期化 ---
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

# --- 4. サイドバー (科目選択) ---
with st.sidebar:
    st.title("🏥 設定")
    # 診療科を選べるようにします
    department = st.selectbox(
        "実習中の診療科を選択",
        options=["内科", "循環器内科", "消化器内科", "外科", "消化器外科", "心臓血管外科", "小児科", "産婦人科", "精神科", "その他"],
        index=0
    )
    st.divider()
    output_length = st.radio(
        "出力のボリューム",
        options=["簡潔に", "標準的", "詳しく"],
        index=1,
        horizontal=True
    )
    st.caption(f"現在の科: **{department}**")
    st.caption("Developed by Hiroto Fujii")

# --- 5. メイン画面 ---
st.title("🩺 Poly-Clinic Support AI")
st.caption("実習の記録を、CBTの知識とレポートへ。")

user_input = st.text_area(
    "実習中の気づきやメモを入力...", 
    placeholder="（例）70代男性、主訴は... 身体所見では...",
    height=180,
    key=f"input_area_{st.session_state.text_key}"
)

# ボタン配置
col1, col2 = st.columns(2)
with col1:
    analyze_btn = st.button("✨ 解析を実行", use_container_width=True, type="primary")
with col2:
    if st.button("🗑️ メモを削除", use_container_width=True):
        st.session_state.res_json = None
        st.session_state.saved = False
        st.session_state.text_key += 1
        st.rerun()

# --- 6. 解析ロジック ---
if analyze_btn:
    if not user_input:
        st.warning("メモを入力してください。")
    else:
        with st.spinner("解析中..."):
            try:
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a medical expert. Response must be in JSON format."
                        },
                        {
                            "role": "user", 
                            "content": f"以下のメモから topic, cbt_knowledge, report_draft を日本語のJSONで作成してください。ボリュームは「{output_length}」で。\n\nメモ: {user_input}"
                        }
                    ],
                    response_format={"type": "json_object"}
                )
                st.session_state.res_json = json.loads(response.choices[0].message.content)
                st.session_state.saved = False
                st.rerun() 
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- 7. 結果表示 & 保存エリア ---
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.markdown(f"### 📌 テーマ: **{data['topic']}**")
    
    tab1, tab2 = st.tabs(["📚 CBT知識", "📝 レポート案"])
    with tab1:
        st.info(data['cbt_knowledge'])
    with tab2:
        st.success(data['report_draft'])

    # 保存ボタンに選択した診療科を表示
    if st.button(f"📥 {department} として保存する", use_container_width=True):
        with st.spinner("Notionに同期中..."):
            try:
                notion.pages.create(
                    parent={"database_id": DATABASE_ID},
                    properties={
                        "Name": {"title": [{"text": {"content": str(data['topic'])}}]},
                        "CBT知識": {"rich_text": [{"text": {"content": str(data['cbt_knowledge'])}}]},
                        "レポート考察": {"rich_text": [{"text": {"content": str(data['report_draft'])}}]},
                        # 【重要】ここに選択した診療科を送る
                        "診療科": {"rich_text": [{"text": {"content": department}}]}
                    }
                )
                st.session_state.saved = True
                st.toast(f"✅ {department} のデータとして保存完了！")
            except Exception as e:
                st.error(f"Notion保存エラー: {e}")
