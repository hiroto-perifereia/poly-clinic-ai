import streamlit as st
import google.generativeai as genai
from notion_client import Client
import json
from PIL import Image

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="CBT & Med-Log AI", page_icon="🎓", layout="centered")

# --- 2. クライアント初期化 ---
# Secretsに GEMINI_API_KEY を追加してください
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash') # 高速・高機能なFlashを採用
notion = Client(auth=st.secrets["NOTION_TOKEN"])
DATABASE_ID = st.secrets["DATABASE_ID"]

# --- 3. セッション状態の初期化 ---
if "res_json" not in st.session_state:
    st.session_state.res_json = None

# --- 4. サイドバー設定 ---
with st.sidebar:
    st.title("⚙️ モード設定")
    mode = st.radio("機能を選択", ["過去問チェッカー", "講義資料・テキスト構造化", "実習メモ"])
    st.divider()
    st.caption("Developed by Hiroto Fujii")

# --- 5. メイン画面 ---
st.title(f"🎓 {mode}")

# ファイルアップロード（画像・PDF）
uploaded_file = st.file_uploader("資料や問題のスクショをアップロード", type=["png", "jpg", "jpeg", "pdf"])

# 補足テキスト入力
user_query = st.text_area(
    "補足・知りたいこと", 
    placeholder="（例）なぜcが間違いなのか教えて / このスライドの重要ポイントをまとめて",
    height=100
)

# 解析ボタン
if st.button("✨ AI解析を実行", use_container_width=True, type="primary"):
    with st.spinner("Geminiが資料を読み解き中..."):
        try:
            # プロンプトの組み立て
            prompt = f"""
            あなたは医学教育のエキスパートです。
            現在のモード: {mode}
            
            指示:
            1. アップロードされた資料（画像/PDF）とユーザーの質問を解析してください。
            2. 以下のJSON形式で回答を生成してください。
            {{
                "topic": "テーマ（疾患名・項目名）",
                "key_points": "CBT/国試に直結する重要知識（改行を含めた箇条書き）",
                "analysis": "詳細な解説や考察（論理的な説明）"
            }}
            
            補足質問: {user_query}
            """
            
            # 画像がある場合とない場合で処理を分け
            content = [prompt]
            if uploaded_file:
                if uploaded_file.type == "application/pdf":
                    # PDF処理（簡易版：最初のページなどを扱う場合は追加実装が必要）
                    st.warning("PDF解析は現在テキスト抽出メインです。画像化してのアップロードを推奨します。")
                else:
                    img = Image.open(uploaded_file)
                    content.append(img)
            
            response = model.generate_content(content)
            # JSON部分を抽出（Geminiの応答からJSONをパース）
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            st.session_state.res_json = json.loads(res_text)
            st.rerun()
            
        except Exception as e:
            st.error(f"解析エラー: {e}")

# --- 6. 結果表示 & 保存 ---
if st.session_state.res_json:
    data = st.session_state.res_json
    st.divider()
    st.markdown(f"### 📌 {data['topic']}")
    
    col_a, col_b = st.tabs(["💡 重要ポイント", "📝 詳細解説"])
    with col_a:
        st.info(data['key_points'])
    with col_b:
        st.success(data['analysis'])

    if st.button("📥 Notionに保存", use_container_width=True):
        try:
            notion.pages.create(
                parent={"database_id": DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": data['topic']}}]},
                    "CBT知識": {"rich_text": [{"text": {"content": data['key_points']}}]},
                    "レポート考察": {"rich_text": [{"text": {"content": data['analysis']}}]},
                    "実習メモ": {"rich_text": [{"text": {"content": f"【{mode}】\n{user_query}"}}]}
                }
            )
            st.toast("Notionに保存完了！")
        except Exception as e:
            st.error(f"Notion保存エラー: {e}")
