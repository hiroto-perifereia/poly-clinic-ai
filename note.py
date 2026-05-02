import streamlit as st
import google.generativeai as genai
from notion_client import Client
import json
from PIL import Image
import datetime

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="CBT & Med-Log AI", page_icon="🎓", layout="centered")

# --- 2. クライアント初期化 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    notion = Client(auth=st.secrets["NOTION_TOKEN"])
    DB_CBT = st.secrets["DATABASE_ID_CBT"]
    DB_LOG = st.secrets["DATABASE_ID_LOG"]
except KeyError as e:
    st.error(f"Secretsが設定されていません: {e}")
    st.stop()

# --- 3. セッション状態の初期化 ---
if "res_json" not in st.session_state:
    st.session_state.res_json = None

# --- 4. サイドバー設定 ---
with st.sidebar:
    st.title("⚙️ 設定")
    mode = st.radio("機能を選択", ["過去問チェッカー", "講義資料・テキスト構造化", "実習メモ"])
    
    if mode == "過去問チェッカー":
        target_db = DB_CBT
        st.info("保存先: CBT弱点データベース")
    else:
        target_db = DB_LOG
        st.info("保存先: 実習ログデータベース")
    
    st.divider()
    st.caption("Developed by Hiroto Fujii")

# --- 5. メイン画面 ---
st.title(f"🎓 {mode}")

# 入力セクション
uploaded_file = st.file_uploader("資料や問題のスクショをアップロード（任意）", type=["png", "jpg", "jpeg"])
user_query = st.text_area("問題文の貼り付け、または補足質問", placeholder="ここに入力...", height=150)

if st.button("✨ AI解析を実行", use_container_width=True, type="primary"):
    if not uploaded_file and not user_query:
        st.warning("画像かテキストのどちらかを入力してください。")
    else:
        with st.spinner("Geminiが解析中..."):
            try:
                # プロンプトの組み立て
                prompt = f"""
                あなたは医学教育エキスパートです。現在のモードは「{mode}」です。
                入力された内容（画像およびテキスト）を解析し、以下のJSON形式で回答してください。
                
                {{
                    "topic": "疾患名またはテーマ",
                    "key_points": "CBT/国試に直結する重要知識（・を使った箇条書き、改行あり）",
                    "analysis": "詳細な解説・誤答選択肢の検討・考察"
                }}
                
                補足質問: {user_query}
                """
                
                inputs = [prompt]
                if uploaded_file:
                    img = Image.open(uploaded_file)
                    inputs.append(img)
                
                response = model.generate_content(inputs)
                # JSON抽出処理
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                st.session_state.res_json = json.loads(res_text)
                st.rerun()
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- 6. 結果表示 & 保存 ---
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.subheader(f"📌 {data['topic']}")
    
    tab1, tab2 = st.tabs(["💡 重要知識", "📝 詳細解説"])
    with tab1:
        st.info(data['key_points'])
    with tab2:
        st.success(data['analysis'])

    if st.button("📥 Notionに保存", use_container_width=True):
        with st.spinner("保存中..."):
            try:
                today = datetime.date.today().isoformat()
                notion.pages.create(
                    parent={"database_id": target_db},
                    properties={
                        "Name": {"title": [{"text": {"content": data['topic']}}]},
                        "CBT知識": {"rich_text": [{"text": {"content": data['key_points']}}]},
                        "レポート考察": {"rich_text": [{"text": {"content": data['analysis']}}]},
                        "実習メモ": {"rich_text": [{"text": {"content": f"【{mode}入力】\n{user_query}"}}]},
                        "日付": {"date": {"start": today}}
                    }
                )
                st.success("Notionへ保存しました！")
                st.session_state.res_json = None # 保存後にクリア
            except Exception as e:
                st.error(f"Notion保存エラー: {e}\n※Notion側のプロパティ名（Name, CBT知識, レポート考察, 実習メモ, 日付）が一致しているか確認してください。")
