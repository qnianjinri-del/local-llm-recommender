import streamlit as st

from detector import get_hardware_info
from online_catalog import fetch_recent_supported_models
from recommender import recommend_from_recent_models
from ollama_backend import (
    check_ollama_running,
    ensure_model_installed,
    is_model_installed,
    list_local_models,
    generate_text,
)

st.set_page_config(page_title="本地模型推荐器", layout="wide")

st.title("本地开源大模型推荐器")
st.write("点击按钮后，程序会读取你的硬件信息，并结合最近模型动态给出推荐。")

if not check_ollama_running():
    st.error("没有检测到 Ollama 正在运行，请先启动 Ollama。")
    st.stop()

if st.button("开始扫描并推荐"):
    hardware = get_hardware_info()
    recent_models = fetch_recent_supported_models(limit_per_family=5)
    recommendations = recommend_from_recent_models(
        recent_models,
        hardware,
        category="general",
    )

    st.session_state["hardware"] = hardware
    st.session_state["recommendations"] = recommendations

if "hardware" in st.session_state:
    st.subheader("硬件信息")
    st.json(st.session_state["hardware"])

if "recommendations" in st.session_state:
    st.subheader("推荐结果")

    recommendations = st.session_state["recommendations"]

    if recommendations:
        for item in recommendations:
            st.write(f"### {item['display_name']}")
            st.write(f"- 部署标签：`{item['deploy_id']}`")
            st.write(f"- 模型家族：{item['family']}")
            st.write(f"- 最近官方模型：{item['source_model_id']}")
            st.write(f"- 最近更新时间：{item['last_modified']}")
            st.write(f"- 说明：{item['notes']}")

            if is_model_installed(item["deploy_id"]):
                st.success("该模型已经安装在本地。")
            else:
                if st.button(f"一键部署 {item['deploy_id']}", key=item["deploy_id"]):
                    with st.spinner(f"正在部署 {item['deploy_id']} ..."):
                        result = ensure_model_installed(item["deploy_id"])
                    st.success(f"{item['deploy_id']} 部署完成。")
                    st.json(result)

            st.divider()
    else:
        st.warning("没有找到适合当前机器的推荐模型。")
st.subheader("测试对话")

local_models = list_local_models()
local_model_ids = [model.get("model") for model in local_models if model.get("model")]

if local_model_ids:
    selected_model = st.selectbox("选择一个已安装模型", local_model_ids)
    user_prompt = st.text_area("输入测试问题", value="请用中文一句话介绍你自己。")

    if st.button("发送测试消息"):
        with st.spinner(f"正在调用 {selected_model} ..."):
            reply = generate_text(selected_model, user_prompt)

        st.write("### 模型回复")
        st.write(reply)
else:
    st.info("当前还没有检测到已安装模型。")