import streamlit as st
import google.generativeai as genai
from notion_client import Client
import json
from PIL import Image
import datetime
import re

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="CBT & Med-Log AI", page_icon="🎓", layout="centered")

# --- 2. クライアント初期化 & モデル自動選別 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    notion = Client(auth=st.secrets["NOTION_TOKEN"])
    DB_CBT = st.secrets["DATABASE_ID_CBT"]
    DB_LOG = st.secrets["DATABASE_ID_LOG"]
except Exception as e:
    st.error(f"初期設定エラー（Secretsを確認してください）: {e}")
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
if "saved" not in st.session_state:
    st.session_state.saved = False

# --- 4. サイドバー設定 ---
with st.sidebar:
    st.title("⚙️ モード設定")
    mode = st.radio("機能を選択", ["過去問チェッカー", "講義資料・テキスト構造化", "実習メモ"])
    target_db = DB_CBT if mode == "過去問チェッカー" else DB_LOG
    st.info(f"保存先: {'CBT用DB' if mode == '過去問チェッカー' else '実習ログDB'}")
    st.caption(f"Active Model: {selected_model}")

# --- 5. メイン画面（入力エリア） ---
st.title(f"🎓 {mode}")

uploaded_file = st.file_uploader("問題や資料のスクショをアップロード", type=["png", "jpg", "jpeg"])
user_query = st.text_area("問題文や補足質問を入力", placeholder="ここに入力...", height=150)

# 【修正ポイント】解析ボタンと削除ボタンを横並びに配置
col_run, col_del_top = st.columns([3, 1]) # 解析ボタンを大きめ(3)、削除を小さめ(1)に

with col_run:
    run_btn = st.button("✨ AI解析を実行", use_container_width=True, type="primary")

with col_del_top:
    # 解析前後のリセット用削除ボタン
    if st.button("🗑️ 削除", use_container_width=True, key="top_delete"):
        if st.session_state.res_json and not st.session_state.saved:
            st.session_state.confirm_delete = True
        else:
            st.session_state.res_json = None
            st.session_state.saved = False
            st.rerun()

# 未保存時の確認メッセージ
if st.session_state.get("confirm_delete"):
    st.warning("⚠️ Notionに保存されていませんが、削除してもいいですか？")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("はい、削除します", use_container_width=True):
            st.session_state.res_json = None
            st.session_state.confirm_delete = False
            st.session_state.saved = False
            st.rerun()
    with c2:
        if st.button("いいえ、戻ります", use_container_width=True):
            st.session_state.confirm_delete = False
            st.rerun()

# 解析処理
if run_btn:
    if not uploaded_file and not user_query:
        st.warning("画像かテキストを入力してください。")
    else:
        with st.spinner("Geminiが解析中..."):
            try:
                prompt = f"あなたは医学教育エキスパートです。モード: {mode}。入力内容を解析し、topic, key_points, analysisを含むJSONで回答してください。質問: {user_query}"
                inputs = [prompt]
                if uploaded_file:
                    inputs.append(Image.open(uploaded_file))
                
                response = model.generate_content(inputs)
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    st.session_state.res_json = json.loads(json_match.group())
                    st.session_state.saved = False
                    st.rerun()
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- 6. 解析結果の表示 & 保存ボタン ---
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.subheader(f"📌 {data.get('topic', '解析結果')}")
    
    tab1, tab2 = st.tabs(["💡 重要ポイント", "📝 詳細解説"])
    with tab1: st.info(data.get('key_points', '情報なし'))
    with tab2: st.success(data.get('analysis', '情報なし'))

    # 保存ボタンは大きく押しやすく配置
    if st.button("📥 Notionに保存", use_container_width=True):
        with st.spinner("保存中..."):
            try:
                today = datetime.date.today().isoformat()
                notion.pages.create(
                    parent={"database_id": target_db},
                    properties={
                        "Name": {"title": [{"text": {"content": str(data.get('topic', '無題'))}}]},
                        "CBT知識": {"rich_text": [{"text": {"content": str(data.get('key_points', ''))}}]},
                        "レポート考察": {"rich_text": [{"text": {"content": str(data.get('analysis', ''))}}]},
                        "実習メモ": {"rich_text": [{"text": {"content": f"【{mode}】\n{user_query}"}}]},
                        "作成日時": {"date": {"start": today}}
                    }
                )
                st.session_state.saved = True
                st.toast("Notionに保存完了！")
            except Exception as e:
                st.error(f"Notion保存エラー: {e}")
