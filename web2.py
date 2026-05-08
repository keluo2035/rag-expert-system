import streamlit as st
import requests
import uuid

# ==========================================
# 1. 核心配置区域 (已填入正式 Production URL)
# ==========================================
N8N_QA_URL = "https://gkl2.app.n8n.cloud/webhook/rag-qa"
N8N_INGEST_URL = "https://gkl2.app.n8n.cloud/webhook/rag-ingest"
N8N_EMAIL_URL = "https://gkl2.app.n8n.cloud/webhook/send-email"

# ==========================================
# 2. 账号与权限系统
# ==========================================
USERS = {
    "user0": {"password": "123456", "role": "admin"},
    "user1": {"password": "123456", "role": "user"},
    "user2": {"password": "123456", "role": "user"},
    "user3": {"password": "123456", "role": "user"},
}


def login():
    st.title("🛡️ 知识库系统登录")
    username = st.text_input("账号")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = USERS[username]["role"]
            # 为每个用户生成/获取持久化的 session_id，用于记住聊天记录
            st.session_state.session_id = f"session_{username}"
            st.rerun()
        else:
            st.error("账号或密码错误")


# ==========================================
# 3. 主界面逻辑
# ==========================================
if "logged_in" not in st.session_state:
    login()
else:
    st.set_page_config(page_title="AI 专家系统 V2", layout="wide")

    # 侧边栏：用户信息与登出
    with st.sidebar:
        st.title(f"👋 你好, {st.session_state.username}")
        st.info(f"权限角色: {st.session_state.role.upper()}")

        # 功能 2：联网开关
        search_mode = st.toggle("🌐 开启联网增强查询", value=False)
        mode_text = "联网" if search_mode else "库内"

        # 功能 1：管理员专属上传
        if st.session_state.role == "admin":
            st.divider()
            st.subheader("📤 管理员工具：入库")
            uploaded_file = st.file_uploader("上传 PDF 文献", type=["pdf"])
            if uploaded_file and st.button("开始向量化入库"):
                with st.spinner("处理中..."):
                    # 这里的 "file" 字段名需与 n8n 中 Data Loader 的配置一致
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    res = requests.post(N8N_INGEST_URL, files=files)
                    if res.status_code == 200:
                        st.success("入库成功！文献已转化为向量存入 Pinecone。")
                    else:
                        st.error(f"入库失败: {res.text}")

        st.divider()
        if st.button("退出登录"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # 功能 4：记住聊天记录（初始化）
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 渲染历史记录
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 聊天输入
    if prompt := st.chat_input(f"正在进行{mode_text}查询..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            try:
                # 构造 Payload，发送联网模式和 session_id
                payload = {
                    "question": prompt,
                    "session_id": st.session_state.session_id,  # 确保 n8n 能够隔离不同用户的 Memory
                    "web_search": search_mode,  # 告诉 n8n 是否启用搜索引擎工具
                    "user_email": st.session_state.username
                }
                response = requests.post(N8N_QA_URL, json=payload, timeout=120)
                response.raise_for_status()

                answer = response.json().get("answer", "解析失败：n8n 返回格式异常")
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

                # 功能 3：发送结果到邮箱
                st.divider()
                st.subheader("📬 结果推送")
                col1, col2 = st.columns([3, 1])
                with col1:
                    target_email = st.text_input("发送至邮箱：", placeholder="2843359601@qq.com", key="email_input")
                with col2:
                    if st.button("确认发送"):
                        email_payload = {
                            "email": target_email,
                            "content": answer,
                            "subject": f"AI 专家查询结果: {prompt[:15]}..."
                        }
                        email_res = requests.post(N8N_EMAIL_URL, json=email_payload)
                        if email_res.status_code == 200:
                            st.toast("✅ 邮件已成功发送至 n8n 队列！")
                        else:
                            st.error("邮件发送失败，请检查 n8n 配置")

            except Exception as e:
                st.error(f"⚠️ 网络请求出错，详细错误：{e}")