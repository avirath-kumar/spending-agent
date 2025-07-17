import streamlit as st
import requests

def send_chat_message(user_message):
    """Send user message to the backend API via POST request"""
    try:
        # Create JSON payload
        payload = {"request": user_message}
        
        # Make POST request to backend
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

def main():
    # Page config
    st.set_page_config(
        page_title="PennyWise - Spending Agent",
        page_icon="💰",
        layout="centered"
    )

    # Custom CSS for centered layout
    st.markdown("""
    <style>
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
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    h1 {
        color: #FFFFFF !important;
    }
    p {
        color: #F5F5F5 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Hide Streamlit default styles
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """

    # Hide Streamlit default styles
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    # Center the content using markdown
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Header with centered image and text
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Center the image using columns within the column
        img_col1, img_col2, img_col3 = st.columns([1, 1, 1])
        with img_col2:
            st.image("spending_agent_icon.png", width=64)
        
        st.markdown('<h1 class="title">PennyWise</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Your intelligent spending companion</p>', unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Chat input - centered without white box
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Chat input
        user_input = st.chat_input("Ask PennyWise about your spending...")
        
        if user_input:
            # Display user message
            st.write(f"**You:** {user_input}")

            # Send to backend and get response
            with st.spinner("PennyWise is thinking..."):
                response = send_chat_message(user_input)
            
            # Display response
            if "error" in response:
                st.error(f"Error: {response['error']}")
            else:
                # Adjust this line based on your backend response structure
                bot_response = response.get('response', response.get('message', str(response)))
                st.write(f"**PennyWise:** {bot_response}")


if __name__ == "__main__":
    main()