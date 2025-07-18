import streamlit as st
import requests
from datetime import datetime
import json

def send_chat_message(user_message, thread_id=None):
    """Send user message to the backend API via POST request"""
    try:
        # Create JSON payload
        payload = {
            "request": user_message,
            "thread_id": thread_id # now includes thread_id for tracking state
        }
        
        # Make POST request to backend
        # LOGGING
        print(f"Sending payload: {payload}")
        response = requests.post(
            "http://localhost:8000/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned status code {response.status_code}"}
    
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend API. Make sure it's running on localhost:8000"}
    except Exception as e:
        return {"error": f"Error sending message: {str(e)}"}

def get_conversation_history(thread_id):
    """ Fetch conversation history from the backend """
    try:
        response = requests.get(f"http://localhost:8000/conversations/{thread_id}")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            return {"error": f"Failed to load conversation: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def display_message(role, content, message_time=None):
    """Display a chat message with proper formatting"""
    if role == "user":
        with st.chat_message("user", avatar="🧑‍💼"):
            st.write(content)
            if message_time:
                st.caption(f"Sent at {message_time}")
    else:
        with st.chat_message("assistant", avatar="💰"):
            st.write(content)
            if message_time:
                st.caption(f"Replied at {message_time}")

def main():
    # Page config
    st.set_page_config(
        page_title="PennyWise - Spending Agent",
        page_icon="💰",
        layout="wide"  # Changed to wide for sidebar
    )

        # Initialize session state variables
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_loaded" not in st.session_state:
        st.session_state.conversation_loaded = False

    # Custom CSS
    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .title {
        color: #F5F5F5 !important;
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0;
        text-align: center;
    }
    .subtitle {
        color: #F5F5F5 !important;
        font-size: 1.2rem;
        margin-top: 0.5rem;
        text-align: center;
    }
    h1, h2, h3 {
        color: #FFFFFF !important;
    }
    p {
        color: #F5F5F5 !important;
    }
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    /* Sidebar contrast improvements */
    section[data-testid="stSidebar"] {
        background: #232946 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #F5F5F5 !important;
    }
    section[data-testid="stSidebar"] .stTextInput > div > input {
        background: #121629 !important;
        color: #F5F5F5 !important;
        border: 1px solid #F5F5F5 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: #393e6e !important;
        color: #F5F5F5 !important;
        border: 1px solid #F5F5F5 !important;
    }
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] .stInfo, section[data-testid="stSidebar"] .stCodeBlock {
        color: #E0E0E0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar for conversation management
    with st.sidebar:
        st.header("💬 Conversations")
        
        # New conversation button
        if st.button("➕ New Conversation", use_container_width=True):
            st.session_state.thread_id = None
            st.session_state.messages = []
            st.session_state.conversation_loaded = False
            st.rerun()
        
        st.divider()
        
        # Current conversation info
        if st.session_state.thread_id:
            st.subheader("Current Thread")
            st.code(st.session_state.thread_id[:8] + "...", language=None)
            st.caption(f"Messages: {len(st.session_state.messages)}")
            
            # Option to clear current conversation
            if st.button("🗑️ Clear Current Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        else:
            st.info("Start a new conversation by sending a message!")
        
        st.divider()
        
        # Load previous conversation by ID
        st.subheader("Load Conversation")
        thread_input = st.text_input("Enter Thread ID:", placeholder="e.g., abc-123-def-456")
        if st.button("📂 Load", use_container_width=True):
            if thread_input:
                # Try to load the conversation
                history = get_conversation_history(thread_input)
                if history and "error" not in history:
                    st.session_state.thread_id = thread_input
                    st.session_state.messages = history.get("messages", [])
                    st.session_state.conversation_loaded = True
                    st.success("Conversation loaded!")
                    st.rerun()
                else:
                    st.error("Conversation not found or error loading")

    # Main content area
    # Header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<h1 class="title">💰 PennyWise</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Your intelligent spending companion</p>', unsafe_allow_html=True)
    
    st.divider()

    # Create a container for the chat history
    chat_container = st.container()
    
    # Load conversation history if we have a thread_id but haven't loaded messages yet
    if st.session_state.thread_id and not st.session_state.conversation_loaded:
        history = get_conversation_history(st.session_state.thread_id)
        if history and "error" not in history:
            st.session_state.messages = history.get("messages", [])
            st.session_state.conversation_loaded = True

    # Display all messages in the conversation
    with chat_container:
        if st.session_state.messages:
            for message in st.session_state.messages:
                display_message(
                    message.get("role", "user"),
                    message.get("content", "")
                )
        else:
            # Welcome message for new conversations
            with st.chat_message("assistant", avatar="💰"):
                st.write("Hello! I'm PennyWise, your intelligent spending companion. Ask me anything about your finances, budgeting, or spending habits!")

    # Chat input at the bottom
    if prompt := st.chat_input("Ask PennyWise about your spending..."):
        # Display user message immediately
        with chat_container:
            display_message("user", prompt)
        
        # Add user message to session state
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Send to backend with thread_id
        with st.spinner("PennyWise is thinking..."):
            response = send_chat_message(prompt, st.session_state.thread_id)
        
        # Handle response
        if "error" in response:
            st.error(f"Error: {response['error']}")
        else:
            # Extract response and thread_id
            bot_response = response.get('response', 'Sorry, I encountered an error.')
            thread_id = response.get('thread_id')
            
            # Update thread_id if this was a new conversation
            if thread_id and not st.session_state.thread_id:
                st.session_state.thread_id = thread_id
                st.session_state.conversation_loaded = True
            
            # Add assistant message to session state
            st.session_state.messages.append({"role": "assistant", "content": bot_response})
            
            # Display assistant message
            with chat_container:
                display_message("assistant", bot_response)
            
            # Force a rerun to update the UI
            st.rerun()

    # Footer with helpful info
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("💡 Tip: You can start a new conversation or load a previous one using the sidebar!")

if __name__ == "__main__":
    main()