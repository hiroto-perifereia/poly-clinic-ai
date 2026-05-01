import streamlit as st
from groq import Groq
from notion_client import Client
import json

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="Medical AI Assistant", page_icon="🩺", layout="centered")

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
    dept_options = ["内科", "循環器内科", "消化器内科", "呼吸器内科", "外科", "消化器外科", "心臓血管外科", "小児科", "産婦人科", "精神科", "その他"]
    department = st.selectbox(
        "実習中の診療科",
        options=dept_options,
        index=None,
        placeholder="診療科を選択..."
    )
    st.divider()
    output_length = st.radio("ボリューム", options=["簡潔に", "標準的", "詳しく"], index=1, horizontal=True)
    st.caption("Developed by Hiroto Fujii")

# --- 5. メメイン画面 ---
st.title("🩺 Poly-Clinic Support AI")
st.caption("実習の記憶を、CBTの知識とレポートへ。")

user_input = st.text_area(
    "実習中の気づきやメモを入力...", 
    placeholder="（例）70代男性、主訴は...",
    height=180,
    key=f"input_area_{st.session_state.text_key}"
)

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
                            "content": f"""
                            以下のメモから情報を抽出し、日本語のJSONで返してください。
                            
                            【出力ルール】
                            - topic: 疾患名やテーマ。
                            - cbt_knowledge: 関連するCBT知識を「・」を用いた箇条書きのテキストとして作成してください。項目ごとに必ず「改行(\\n)」を入れて、読みやすい箇条書きのテキストにしてください。辞書形式やオブジェクト形式にはせず、必ず一つの「文字列」にしてください。
                            - report_draft: 実習レポートの考察案。
                            
                            ボリュームは「{output_length}」で。
                            
                            メモ: {user_input}
                            """
                        }
                    ],
                    response_format={"type": "json_object"}
                )
                res = json.loads(response.choices[0].message.content)
                
                # 万が一AIがリストや辞書で返してきた場合のバックアップ処理
                if not isinstance(res.get('cbt_knowledge'), str):
                    res['cbt_knowledge'] = str(res['cbt_knowledge'])
                
                st.session_state.res_json = res
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

    if department is None:
        st.warning("保存するにはサイドバーで診療科を選択してください。")
        st.button("📥 保存不可 (診療科未選択)", use_container_width=True, disabled=True)
    else:
        if st.button(f"📥 {department} として保存", use_container_width=True):
            with st.spinner("Notionに同期中..."):
                try:
                    notion.pages.create(
                        parent={"database_id": DATABASE_ID},
                        properties={
                            "Name": {"title": [{"text": {"content": str(data['topic'])}}]},
                            "CBT知識": {"rich_text": [{"text": {"content": str(data['cbt_knowledge'])}}]},
                            "レポート考察": {"rich_text": [{"text": {"content": str(data['report_draft'])}}]},
                            "診療科": {"select": {"name": department}},
                            # 【追加】入力した生のメモをそのまま保存する
                            "実習メモ": {"rich_text": [{"text": {"content": user_input}}]}
                            "作成日時": {"date": {"start": today}}
                        }
                    )
                    st.session_state.saved = True
                    st.toast(f"✅ メモと解析結果を {department} に保存しました！")
                except Exception as e:
                    st.error(f"Notion保存エラー: {e}")
