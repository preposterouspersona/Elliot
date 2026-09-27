import os
import shutil
import time
import streamlit as st
from main import elliot_system

# Configure page layout
st.set_page_config(
    page_title="Elliot",
    layout="wide",
    initial_sidebar_state="expanded"
)

# High-Contrast Ultramarine Theme CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Global App Background */
    .stApp {
        background-color: #EEF2FF;
        color: #0F172A;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    /* Hide Streamlit Clutter */
    header[data-testid="stHeader"] { display: none !important; }
    footer { display: none !important; }
    #MainMenu { display: none !important; }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #E0E7FF !important;
        border-right: 1px solid #C7D2FE !important;
    }
    .stSidebar [data-testid="stMarkdownContainer"] h3 {
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #4338CA;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    .stSidebar [data-testid="stMarkdownContainer"] p {
        color: #312E81;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* 1. SIDEBAR INPUT FIELDS */
    .stTextInput input, .stNumberInput input {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #818CF8 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
    }

    /* 2. EXPANDERS */
    .stExpander {
        background-color: #FFFFFF !important;
        border: 1px solid #C7D2FE !important;
        border-radius: 8px !important;
        margin-bottom: 1rem !important;
    }
    .stExpander summary {
        color: #312E81 !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }

    /* 3. CODE BLOCKS (THE FIX: Light background to support the dark text) */
    div[data-testid="stCodeBlock"], pre {
        background-color: #F8FAFC !important; /* Very light, clean slate background */
        border: 1px solid #CBD5E1 !important; /* Soft border */
        border-radius: 8px !important;
    }
    
    /* Ensure the base code text is dark enough if a token class misses it */
    div[data-testid="stCodeBlock"] code, pre code {
        color: #0F172A !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* 4. CHAT INPUT */
    [data-testid="stChatInput"] {
        background-color: #FFFFFF !important;
        border: 1px solid #818CF8 !important;
        border-radius: 10px !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #0F172A !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* Main Header */
    .elliot-header {
        padding: 1.5rem 0 1.5rem 0;
        border-bottom: 2px solid #C7D2FE;
        margin-bottom: 1.5rem;
    }
    .elliot-header h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 400;
        font-size: 2.25rem;
        letter-spacing: -0.04em;
        margin: 0;
        color: #312E81;
    }
    .elliot-header h1 strong {
        font-weight: 700;
        color: #0F172A;
    }
    .elliot-header p {
        color: #4338CA;
        font-size: 0.85rem;
        margin-top: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }

    /* Chat Message Text */
    .stChatMessage {
        background-color: transparent !important;
        padding: 1rem 0 !important;
    }
    .stChatMessage p {
        color: #0F172A !important;
    }

    /* Avatars */
    [data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {
        background-color: #4F46E5 !important;
        color: #FFFFFF !important;
        font-weight: 600;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

# Main Title Area
st.markdown("""
    <div class="elliot-header">
        <h1><strong>ELLIOT.</strong></h1>
        <p>PostgreSQL Operations & Analytics</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.markdown("### SYSTEM CONFIGURATION")
st.sidebar.markdown("PostgreSQL Connection Parameters")

db_config = {
    "host": st.sidebar.text_input("HOST", value=os.getenv("host", "localhost")),
    "port": int(st.sidebar.number_input("PORT", value=int(os.getenv("port", 5432)))),
    "dbname": st.sidebar.text_input("DATABASE", value=os.getenv("database") or os.getenv("dbname") or "postgres"),
    "user": st.sidebar.text_input("USER", value=os.getenv("user", "postgres")),
    "password": st.sidebar.text_input("PASSWORD", type="password", value=os.getenv("password", ""))
}

# Ensure charts directory exists
os.makedirs("charts", exist_ok=True)

# Chat State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Display SQL if present
        if msg.get("sql"):
            with st.expander("Show Generated SQL Query"):
                st.code(msg["sql"], language="sql")
                
        # Display Python code if present
        if msg.get("python"):
            with st.expander("Show Visualization Code"):
                st.code(msg["python"], language="python")
                
        # Display saved chart image
        if msg.get("chart") and os.path.exists(msg["chart"]):
            st.image(msg["chart"], use_container_width=True)

# Chat Input & Execution
if prompt := st.chat_input("Enter system query or operational command..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing operation..."):
            initial_state = {
                "user_prompt": prompt,
                "db_config": db_config,
                "messages": []
            }

            try:
                # Invoke the LangGraph workflow safely
                output = elliot_system.invoke(initial_state)

                final_ans = output.get("final_answer", "System returned no output.")
                generated_sql = output.get("generated_sql_query", None)
                python_code = output.get("python_code", None)
                chart_file = output.get("chart_path", None)

                # Display final answer text
                st.markdown(final_ans)

                # Debug expanders
                if generated_sql and not generated_sql.startswith("-- Error"):
                    with st.expander("Show Generated SQL Query"):
                        st.code(generated_sql, language="sql")

                if python_code and not python_code.startswith("# Error"):
                    with st.expander("Show Visualization Code"):
                        st.code(python_code, language="python")

                # Handle persistent chart copying
                saved_chart_path = None
                if chart_file and os.path.exists(chart_file):
                    unique_filename = f"charts/chart_{int(time.time())}.png"
                    shutil.copy(chart_file, unique_filename)
                    saved_chart_path = unique_filename
                    st.image(saved_chart_path, use_container_width=True)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_ans,
                    "sql": generated_sql,
                    "python": python_code,
                    "chart": saved_chart_path
                })
                
            except Exception as e:
                error_message = f"**System Error:** Connection or processing failed.\n\n`Details: {str(e)}`\n\nPlease check your configuration and try again."
                st.error(error_message)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_message
                })