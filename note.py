import streamlit as st
import google.generativeai as genai
from notion_client import Client
import json
from PIL import Image
import datetime

# --- 2. クライアント初期化 & モデル自動選別 ---
# Secretsから取得
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    notion = Client(auth=st.secrets["NOTION_TOKEN"])
    
    # データベースIDをそれぞれ取得
    DB_CBT = st.secrets["DATABASE_ID_CBT"]
    DB_LOG = st.secrets["DATABASE_ID_LOG"]
except KeyError as e:
    st.error(f"Secrets設定（{e}）が見つかりません。")
    st.stop()

def get_best_model():
    """利用可能な最新モデルを自動取得"""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash-latest', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for target in priority:
            if target in models: return target
        return models[0] if models else "gemini-1.5-flash"
    except:
        return "gemini-1.5-flash"

model = genai.GenerativeModel(get_best_model())

# --- 4. サイドバー設定（ここで保存先を切り替え） ---
with st.sidebar:
    st.title("⚙️ モード設定")
    mode = st.radio("機能を選択", ["過去問チェッカー", "講義資料・テキスト構造化", "実習メモ"])
    
    # 【重要】モードに応じて target_db を決定
    if mode == "過去問チェッカー":
        target_db = DB_CBT
        st.info("保存先: CBT用データベース")
    else:
        # 講義資料と実習メモは実習ログDBへ
        target_db = DB_LOG
        st.info("保存先: 実習ログデータベース")

# --- (中略: 解析ロジックなど) ---

# --- 6. 保存ボタンの処理 ---
if st.button("📥 Notionに保存", use_container_width=True):
    with st.spinner("保存中..."):
        try:
            today = datetime.date.today().isoformat()
            # target_db 変数を使って保存先を出し分ける
            notion.pages.create(
                parent={"database_id": target_db},
                properties={
                    "Name": {"title": [{"text": {"content": data['topic']}}]},
                    "CBT知識": {"rich_text": [{"text": {"content": data['key_points']}}]},
                    "レポート考察": {"rich_text": [{"text": {"content": data['analysis']}}]},
                    "実習メモ": {"rich_text": [{"text": {"content": f"【{mode}】\n{user_query}"}}]},
                    "日付": {"date": {"start": today}}
                }
            )
            st.success(f"【{mode}】としてNotionに保存しました！")
        except Exception as e:
            st.error(f"保存エラー: {e}")
