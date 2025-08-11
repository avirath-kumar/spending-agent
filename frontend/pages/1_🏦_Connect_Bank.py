import streamlit as st
import requests
import json
import time

def main():
    st.set_page_config(page_title="Connect Bank - PennyWise", page_icon="🏦")
    
    st.title("🏦 Connect Your Bank Account")
    st.markdown("Securely connect your bank account to start tracking your spending.")
    
    # Initialize session state
    if 'link_token' not in st.session_state:
        st.session_state.link_token = None
    if 'waiting_for_link' not in st.session_state:
        st.session_state.waiting_for_link = False
    
    # Check for connected accounts
    try:
        response = requests.get("http://localhost:8000/plaid/accounts")
        if response.status_code == 200:
            accounts = response.json()
            if accounts:
                st.success(f"✅ You have {len(accounts)} connected account(s)")
                
                # Display accounts
                for acc in accounts:
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{acc['name']}** ({acc['institution']})")
                    with col2:
                        st.write(f"${acc['balance']:,.2f}")
                    with col3:
                        st.write(f"{acc['type']}")
                
                st.divider()
    except:
        pass
    
    # Method 1: External Link Approach (Recommended)
    st.subheader("Method 1: Connect via Secure Link (Recommended)")
    
    if st.button("🔗 Generate Secure Connection Link", type="primary", key="method1"):
        with st.spinner("Creating secure link..."):
            try:
                response = requests.post("http://localhost:8000/plaid/link-token")
                if response.status_code == 200:
                    link_token = response.json()["link_token"]
                    st.session_state.link_token = link_token
                    
                    # Create a link to open Plaid Link in a new tab
                    # You'll need to create a simple HTML page that handles Plaid Link
                    plaid_link_url = f"http://localhost:8000/plaid/link-page?token={link_token}"
                    
                    st.success("✅ Secure link created!")
                    st.info(f"""
                    **Next Steps:**
                    1. Click the link below to open Plaid Link in a new window
                    2. Complete the bank connection process
                    3. Return to this page and click "Check Connection Status"
                    
                    [🏦 Open Plaid Link]({plaid_link_url})
                    """)
                    
                    st.session_state.waiting_for_link = True
                else:
                    st.error("Failed to create link token")
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    # Manual sync button
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("🔄 Sync Transactions")
        st.caption("Fetch the latest transactions from your connected accounts")
    with col2:
        if st.button("Sync Now"):
            with st.spinner("Syncing transactions..."):
                try:
                    response = requests.post("http://localhost:8000/plaid/sync-transactions")
                    if response.status_code == 200:
                        result = response.json()
                        st.success(
                            f"✅ Sync complete! "
                            f"Added: {result['added']}, "
                            f"Modified: {result['modified']}, "
                            f"Removed: {result['removed']}"
                        )
                    else:
                        st.error("Sync failed")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()