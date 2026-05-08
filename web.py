import streamlit as st
import requests
import uuid

# ==========================================
# 1. 核心配置区域 (请替换为你的 n8n Production URL)
# ==========================================
N8N_QA_URL = "https://gkl2.app.n8n.cloud/webhook/rag-qa"
N8N_INGEST_URL = "https://gkl2.app.n8n.cloud/webhook/rag-ingest"

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
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    res = requests.post(N8N_INGEST_URL, files=files)
                    if res.status_code == 200: st.success("入库成功")

        if st.button("退出登录"):
            del st.session_state.logged_in
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
                    "session_id": st.session_state.session_id,  # 功能 4 关键
                    "web_search": search_mode,  # 功能 2 关键
                    "user_email": st.session_state.username  # 用于标识是谁在问
                }
                response = requests.post(N8N_QA_URL, json=payload, timeout=120)
                answer = response.json().get("answer", "解析失败")
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

                # 功能 3：发送结果到邮箱
                st.divider()
                target_email = st.text_input("📧 将此回答发送至邮箱：", placeholder="2843359601@qq.com")
                if st.button("确认发送"):
                    # 这里向 n8n 发送一个专门的邮件触发请求
                    email_payload = {"email": target_email, "content": answer,
                                     "subject": f"AI 查询结果: {prompt[:10]}..."}
                    # 假设你单独配置了一个邮件 Webhook
                    requests.post("你的_N8N_邮件_WEBHOOK_URL", json=email_payload)
                    st.toast("邮件发送请求已提交！")

            except Exception as e:
                st.error(f"连接失败: {e}")