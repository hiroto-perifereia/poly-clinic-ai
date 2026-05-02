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
    """利用可能な最新モデルを自動取得"""
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
    st.title("⚙️ モード設定")
    mode = st.radio("機能を選択", ["過去問チェッカー", "講義資料・テキスト構造化", "実習メモ"])
    
    # モードによって保存先IDを決定
    if mode == "過去問チェッカー":
        target_db = DB_CBT
        st.info("保存先: CBT用DB")
    else:
        target_db = DB_LOG
        st.info("保存先: 実習ログDB")
    
    st.caption(f"Active Model: {selected_model}")
    if st.button("結果をクリア"):
        st.session_state.res_json = None
        st.rerun()

# --- 5. メイン画面（入力エリア） ---
st.title(f"🎓 {mode}")

uploaded_file = st.file_uploader("問題や資料のスクショをアップロード", type=["png", "jpg", "jpeg"])
user_query = st.text_area("問題文の貼り付け、またはAIへの質問", placeholder="例：なぜbは誤り？ / このスライドを要約して", height=150)

if st.button("✨ AI解析を実行", use_container_width=True, type="primary"):
    if not uploaded_file and not user_query:
        st.warning("画像かテキストを入力してください。")
    else:
        with st.spinner("Geminiが解析中..."):
            try:
                prompt = f"""
                あなたは医学教育のエキスパートです。モード: {mode}
                入力内容を解析し、必ず以下のJSON形式のみで回答してください。
                他の解説文などは一切含めないでください。
                
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
                response_text = response.text
                
                # 正規表現でJSON部分だけを抽出
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                
                if json_match:
                    res_text = json_match.group()
                    st.session_state.res_json = json.loads(res_text)
                    st.rerun()
                else:
                    st.error("AIの応答からデータが見つかりませんでした。")
                    st.write("AIの生応答:", response_text)
                    
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- 6. 解析結果の表示 & Notion保存 ---
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.subheader(f"📌 {data.get('topic', '解析結果')}")
    
    tab1, tab2 = st.tabs(["💡 重要ポイント", "📝 詳細解説"])
    with tab1:
        st.info(data.get('key_points', '情報なし'))
    with tab2:
        st.success(data.get('analysis', '情報なし'))

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
                        "日付": {"date": {"start": today}}
                    }
                )
                st.success(f"Notion（{mode}）に保存完了！")
            except Exception as e:
                st.error(f"Notion保存エラー: {e}")
