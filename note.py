import streamlit as st
import google.generativeai as genai
from notion_client import Client
import json
from PIL import Image
import datetime

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="CBT & Med-Log AI", page_icon="🎓", layout="centered")

# --- 2. クライアント初期化 & モデル自動選別 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    notion = Client(auth=st.secrets["NOTION_TOKEN"])
    DB_CBT = st.secrets["DATABASE_ID_CBT"]
    DB_LOG = st.secrets["DATABASE_ID_LOG"]
except Exception as e:
    st.error(f"初期設定エラー: {e}")
    st.stop()

def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash-latest', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for target in priority:
            if target in models: return target
        return models[0] if models else "gemini-1.5-flash"
    except:
        return "gemini-1.5-flash"

selected_model = get_best_model()
model = genai.GenerativeModel(selected_model)

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
    
    st.caption(f"Active Model: {selected_model}")

# --- 5. メイン画面（入力エリア） ---
st.title(f"🎓 {mode}")

# ここが消えていた可能性があります
uploaded_file = st.file_uploader("資料や問題のスクショをアップロード（任意）", type=["png", "jpg", "jpeg"])
user_query = st.text_area("問題文の貼り付け、または補足質問", placeholder="ここに入力してください...", height=150)

if st.button("✨ AI解析を実行", use_container_width=True, type="primary"):
    if not uploaded_file and not user_query:
        st.warning("画像かテキストを入力してください。")
    else:
        with st.spinner("Geminiが解析中..."):
            try:
                prompt = f"""
                あなたは医学教育のエキスパートです。モード: {mode}
                入力内容を解析し、以下のJSON形式で回答してください。
                {{
                    "topic": "テーマ（疾患名など）",
                    "key_points": "CBT知識（・で箇条書き、改行あり）",
                    "analysis": "詳細な解説・考察"
                }}
                補足質問: {user_query}
                """
                
                inputs = [prompt]
                if uploaded_file:
                    inputs.append(Image.open(uploaded_file))
                
                response = model.generate_content(inputs)
                # JSON抽出（エラー回避用）
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                st.session_state.res_json = json.loads(res_text)
                st.rerun()
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- 6. 解析結果の表示 & Notion保存ボタン ---
# 解析が完了している場合のみ、以下のブロックが表示されます
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.subheader(f"📌 {data['topic']}")
    
    col1, col2 = st.tabs(["💡 重要知識", "📝 詳細解説"])
    with col1:
        st.info(data['key_points'])
    with col2:
        st.success(data['analysis'])

    # 保存処理
    if st.button("📥 Notionに保存", use_container_width=True):
        with st.spinner("保存中..."):
            try:
                today = datetime.date.today().isoformat()
                notion.pages.create(
                    parent={"database_id": target_db}, # 動的に切り替え
                    properties={
                        "Name": {"title": [{"text": {"content": data['topic']}}]},
                        "CBT知識": {"rich_text": [{"text": {"content": data['key_points']}}]},
                        "レポート考察": {"rich_text": [{"text": {"content": data['analysis']}}]},
                        "実習メモ": {"rich_text": [{"text": {"content": f"【{mode}】\n{user_query}"}}]},
                        "日付": {"date": {"start": today}}
                    }
                )
                st.success(f"【{mode}】としてNotionに保存しました！")
                # 保存後に結果を消したくない場合はここをコメントアウト
                # st.session_state.res_json = None 
            except Exception as e:
                st.error(f"Notion保存エラー: {e}")
