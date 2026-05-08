import streamlit as st
import requests
import uuid

# ==========================================
# 1. 全局配置区域
# ==========================================
# 【重要提醒】：请将这里的 URL 替换为你 n8n 中对应 Webhook 的 Production URL (生产环境地址，不带 -test)
# 问答接口地址 (刚才一直用的那个)
N8N_QA_URL = "https://gkl2.app.n8n.cloud/webhook/rag-qa"
# 文件上传/入库接口地址 (你在新建的 RAG Ingestion 流水线里配置的 Webhook 地址)
N8N_INGEST_URL = "https://gkl2.app.n8n.cloud/webhook/rag-ingest"

# ==========================================
# 2. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="AI 知识库专家系统", page_icon="🤖", layout="wide")
st.title("🎓 企业级知识库 AI 专家")
st.caption("Powered by Qwen2.5-7B, Pinecone & n8n Workflow")

# ==========================================
# 3. 初始化 Session 状态 (记忆隔离与对话历史)
# ==========================================
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex

if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 4. 左侧边栏：知识库管理 (文件上传)
# ==========================================
with st.sidebar:
    st.header("📚 知识库管理")
    st.markdown("请在此上传您的专业文献，AI 将自动切割并存入向量数据库。")

    # 文件上传组件，限制只能传 PDF
    uploaded_file = st.file_uploader("选择 PDF 文件", type=["pdf"])

    if uploaded_file is not None:
        # 当点击“一键入库”按钮时触发
        if st.button("🚀 一键解析并入库", use_container_width=True):
            with st.spinner("正在上传并进行向量化处理，这可能需要几分钟，请不要关闭页面..."):
                try:
                    # 将文件打包成请求需要的 multipart/form-data 格式
                    # 注意：n8n 默认接收的字段名通常为 'file'
                    files = {
                        "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")
                    }

                    # 发送请求给 n8n 的入库流水线 (设定 300秒 超时，因为解析长文档慢)
                    response = requests.post(
                        N8N_INGEST_URL,
                        files=files,
                        timeout=300,
                        proxies={"http": None, "https": None}
                    )

                    response.raise_for_status()
                    result = response.json()

                    # 如果 n8n 返回了成功标志
                    if result.get("status") == "success":
                        st.success(f"✅ {uploaded_file.name} 入库成功！\n\n{result.get('message', '')}")
                    else:
                        st.warning("⚠️ 上传完毕，但 n8n 返回的状态未知，请检查 n8n 日志。")

                except requests.exceptions.Timeout:
                    st.error("⏳ 处理超时：文件过大或模型嵌入计算太久，请查看 n8n 后台是否仍在处理。")
                except Exception as e:
                    st.error(f"❌ 上传失败，详细错误：{e}")

    st.divider()
    st.caption(f"当前会话 ID: \n`{st.session_state.session_id}`")

# ==========================================
# 5. 主体区域：核心对话逻辑
# ==========================================
# 每次刷新页面时，重新渲染历史聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 监听用户在底部聊天框的输入
if prompt := st.chat_input("请输入您的问题，例如：总结一下刚刚上传的文献核心观点"):

    # 将用户的问题显示在界面上，并存入历史记录
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 开启助手的回复气泡，并显示加载动画
    with st.chat_message("assistant"):
        with st.spinner("AI 正在检索知识库并思考回答，请稍候..."):
            try:
                # 发给问答流水线的数据
                payload = {
                    "question": prompt,
                    "session_id": st.session_state.session_id
                }

                # 发起跨国 HTTP 请求 (带防代理护盾)
                response = requests.post(
                    N8N_QA_URL,
                    json=payload,
                    timeout=180,
                    proxies={"http": None, "https": None}
                )

                response.raise_for_status()
                result = response.json()

                # 获取 n8n 的回答
                answer = result.get("answer", "⚠️ n8n 处理成功，但未返回 'answer' 字段。")

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except requests.exceptions.Timeout:
                st.error("⏳ 请求超时：计算时间过长（超过3分钟），本次请求已中断。")
            except Exception as e:
                st.error(f"❌ 网络请求出错，详细错误：{e}")