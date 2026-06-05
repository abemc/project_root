import streamlit as st
import os
from dotenv import load_dotenv

# .envファイルのロード
load_dotenv()

# アプリのヘッダー設定
st.set_page_config(page_title="Prompt Engineering Playground", page_icon="✍️", layout="wide")

st.title("✍️ Prompt Engineering Playground (プロンプト実験場)")
st.caption("LLMに送られるプロンプトの「中身」を視覚的に理解し、プロンプトの設計手法（System Prompt, Few-Shot 等）の効果を体験するツールです。")

# デフォルトのAPIキーの読み込み
env_api_key = os.getenv("OPENAI_API_KEY") or ""

# サイドバー設定
st.sidebar.header("⚙️ 設定・APIキー")
api_key = st.sidebar.text_input(
    "OpenAI API Key (任意)", 
    value=env_api_key,
    type="password", 
    help="APIキーを入力すると、実際にChatGPTから回答を取得できます。未入力の場合は擬似モックが応答します。手動入力した後は必ず Enter キーを押して確定してください。"
)
temperature = st.sidebar.slider("Temperature (温度 / 創造性)", min_value=0.0, max_value=1.0, value=0.7, step=0.1, help="値が大きいほどランダムで創造的な回答になり、小さいほど決定論的で堅実な回答になります。")

# APIキー適用状態のバッジ表示
if api_key:
    st.sidebar.success("🔑 APIキーが適用されています (OpenAI)")
else:
    st.sidebar.info("💡 モックモードで動作中 (APIキー未設定)")

# モックモード強制チェックボックス (接続エラーや無効なキーでのブロックを回避するため)
force_mock = st.sidebar.checkbox(
    "🤖 モックモードを強制する", 
    value=not api_key, 
    help="オンにすると、APIキーが設定されていてもOpenAIへの通信を行わず、ローカルの擬似モックで動作します。ネットワークエラーやAPIキーが無効な場合に便利です。"
)

# メイン画面のレイアウト
col_inputs, col_preview = st.columns([1.1, 0.9])

with col_inputs:
    st.header("📝 プロンプト構成要素の設計")
    
    # 1. System Prompt
    system_prompt = st.text_area(
        "🧠 System Prompt (システムプロンプト / 役割定義)",
        value="あなたは親切で簡潔なアシスタントです。回答には必ず1つの絵文字を含めてください。",
        height=100,
        help="LLMの全体的なペルソナ（性格や役割、ルール）を指定します。"
    )
    
    # 2. Few-shot Examples
    use_few_shot = st.checkbox("💡 Few-shot Examples (例示) を追加する", value=False)
    few_shot_content = ""
    if use_few_shot:
        few_shot_content = st.text_area(
            "Examples (入力と出力のペア例)",
            value="質問: 赤い果物といえば？\n回答: りんごです！🍎\n\n質問: 黄色い乗り物といえば？\n回答: ドクターイエローです！🚄",
            height=120,
            help="いくつかの入出力例（Shot）を示すことで、LLMに出力フォーマットやトーン＆マナーを学習させます。"
        )
        
    # 3. User Input
    user_input = st.text_area(
        "👤 User Prompt (ユーザーの質問)",
        value="青い自然のものといえば？",
        height=80,
        help="ユーザーがLLMに尋ねたい具体的な質問文です。"
    )
    
    # 左側にも送信ボタンを配置して、入力を終えたらすぐに送信できるように改善
    run_button_left = st.button("🚀 LLMを呼び出す (送信)", key="run_left", type="primary")

# 右側: プレビューと実行結果
with col_preview:
    st.header("🔍 プレビュー & 実行結果")
    
    # プロンプトの結合・シミュレート
    st.write("**LLMに送信されるプロンプトの構造イメージ:**")
    
    # メッセージの組み立てプレビュー
    with st.expander("👀 結合されたプロンプト全体の表示", expanded=True):
        preview_text = ""
        preview_text += f"💡 [SYSTEM ROLE]\n{system_prompt}\n\n"
        if use_few_shot and few_shot_content:
            preview_text += f"💡 [FEW-SHOT EXAMPLES]\n{few_shot_content}\n\n"
        preview_text += f"💡 [USER INPUT]\n{user_input}"
        
        st.code(preview_text, language="markdown")
        
    # 右側の送信ボタン
    run_button_right = st.button("🚀 LLMを呼び出す (プ�            # 入力プロンプトのトーンやキーワードを解析した擬似応答の生成
            mock_reply = ""
            q = user_input.lower().replace("　", " ").strip()
            
            if any(x in q for x in ["llm", "言語モデル", "えるえるえむ", "エルエルエム"]):
                mock_reply = "LLM（大規模言語モデル）は、膨大なテキストデータから言葉のパターンを学習したAIです。文章生成や翻訳、質問回答などが得意です。🤖"
            elif any(x in q for x in ["rag", "検索拡張", "らぐ", "ラグ"]):
                mock_reply = "RAG（検索拡張生成）は、信頼できる外部データベースから検索した情報をLLMに渡して回答させることで、嘘（ハルシネーション）を激減させる技術です。🔍"
            elif any(x in q for x in ["python", "パイソン", "ぱいそん", "プログラミング"]):
                mock_reply = "Pythonは、シンプルで読みやすいコードが特徴のプログラミング言語です。AI開発やデータサイエンスのデファクトスタンダードとなっています。🐍"
            elif any(x in q for x in ["量子力学", "量子", "りょうし"]):
                if "5歳" in system_prompt or "子供" in system_prompt:
                    mock_reply = "量子力学はね、目に見えないとってもとっても小さなミクロの世界の不思議なルールをお勉強する科学だよ！まほうみたいに、同時に2つの場所にいたりするんだ！🔮"
                else:
                    mock_reply = "量子力学は、分子や原子、素粒子といった極微のスケールにおける物理現象を説明する物理学の理論です。重ね合わせや量子もつれといった、日常とは異なる法則が働きます。🌀"
            elif any(x in q for x in ["青", "自然", "海", "空", "blue", "nature"]):
                if "簡潔" in system_prompt or "短く" in system_prompt:
                    mock_reply = "海や空です。🌐"
                elif "英語" in system_prompt.lower() or "english" in system_prompt.lower():
                    mock_reply = "It is the ocean or the sky! 🌊"
                else:
                    mock_reply = "青い自然のものとしては、広大な「海」や澄み渡る「空」などが代表的ですね！🌊"
            elif any(x in q for x in ["こんにちは", "ハロー", "hello", "はじめまして"]):
                mock_reply = "こんにちは！おもちゃのモックAIアシスタントです。何か質問はありますか？✨"
            else:
                emoji = "💡"
                if "絵文字" in system_prompt:
                    emoji = "✨"
                
                if "簡潔" in system_prompt or "短く" in system_prompt:
                    mock_reply = f"「{user_input[:15]}...」についてですね。モックモードのため簡潔にお答えします。{emoji}"
                else:
                    mock_reply = f"ご質問「{user_input}」についてですね！現在はAPI接続なしで動作する【デモ用モックモード】であるため、自由な回答生成はできませんが、APIキーをサイドバーに正しく設定すると、本物のAIがこの質問に対して自動で的確な回答を生成します。{emoji}"
                
            st.write(mock_reply)�ご確認ください。ローカルでプロンプトの実験を続けたい場合は、サイドバーの「🤖 モックモードを強制する」にチェックを入れてください。")
                with st.expander("詳細なエラーログを表示"):
                    st.exception(e)
        else:
            # モック応答
            st.markdown("##### 🟡 デモ用モック応答 (APIキー未設定)")
            st.info("💡 APIキーが指定されていないため、入力内容に基づいた擬似的なモック応答をシミュレーションしています。")
            
            # 入力プロンプトのトーンやキーワードを解析した擬似応答の生成
            mock_reply = ""
            q = user_input.lower()
            
            if "llm" in q or "大文字" in q or "言語モデル" in q:
                mock_reply = "LLM（大規模言語モデル）は、膨大なテキストデータから言葉のパターンを学習したAIです。文章生成や翻訳、質問回答などが得意です。🤖"
            elif "rag" in q or "検索拡張" in q:
                mock_reply = "RAG（検索拡張生成）は、信頼できる外部データベースから検索した情報をLLMに渡して回答させることで、嘘（ハルシネーション）を激減させる技術です。🔍"
            elif "python" in q or "パイソン" in q:
                mock_reply = "Pythonは、シンプルで読みやすいコードが特徴のプログラミング言語です。AI開発やデータサイエンスのデファクトスタンダードとなっています。🐍"
            elif "量子力学" in q or "量子" in q:
                if "5歳" in system_prompt or "子供" in system_prompt:
                    mock_reply = "量子力学はね、目に見えないとってもとっても小さなミクロの世界の不思議なルールをお勉強する科学だよ！まほうみたいに、同時に2つの場所にいたりするんだ！🔮"
                else:
                    mock_reply = "量子力学は、分子や原子、素粒子といった極微のスケールにおける物理現象を説明する物理学の理論です。重ね合わせや量子もつれといった、日常とは異なる法則が働きます。🌀"
            else:
                emoji = "💡"
                if "絵文字" in system_prompt:
                    emoji = "✨"
                
                if "簡潔" in system_prompt or "短く" in system_prompt:
                    mock_reply = f"「{user_input[:15]}...」についてですね。モックモードのため詳細な回答はできませんが、APIキーを設定するとChatGPTから本物の回答が生成されます。{emoji}"
                else:
                    mock_reply = f"ご質問「{user_input}」についてですね！現在はAPIキー未設定の【デモ用モックモード】で動作しているため、本物のLLMによる自由な生成は行われませんが、APIキーをサイドバーに設定すると、この質問に対する本物のAI回答がリアルタイムで出力されます。{emoji}"
                
            st.write(mock_reply)

# 学習のための補足
st.markdown("---")
st.header("💡 プロンプトエンジニアリングの基本テクニック解説")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("""
    ### 1. ペルソナ（役割）の付与
    System Prompt に「あなたは〇〇の専門家です」と書くだけで、LLMの語彙や説明の深さが大きく変わります。
    
    **実験例**: System Prompt に `あなたは5歳の子供向けに説明する学校の先生です。` と入力して、難しい質問（「量子力学って何？」など）を投げてみましょう。
    """)
with col_b:
    st.markdown("""
    ### 2. Few-shot（例示）の効果
    言葉でルールを事細かに説明するよりも、数個の「お手本」を見せる方が、LLMは望んだフォーマットやルール（出力の長さ、口調、JSON形式など）を遥かに正確に真似してくれます。
    
    **実験例**: チェックボックスをオンにし、入出力例のパターン（`質問 ➡️ 返答`）を定義した上で、新しい質問を投げてみましょう。
    """)
