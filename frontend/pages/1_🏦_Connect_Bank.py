import streamlit as st
import requests
import streamlit.components.v1 as components

def main():
    st.set_page_config(page_title="Connect Bank - PennyWise", page_icon="🏦")
    
    st.title("🏦 Connect Your Bank Account")
    st.markdown("Securely connect your bank account to start tracking your spending.")
    
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
    
    # Connect new account section
    if st.button("➕ Connect New Bank Account", type="primary"):
        with st.spinner("Initializing secure connection..."):
            # Get link token from backend
            try:
                response = requests.post("http://localhost:8000/plaid/link-token")
                if response.status_code == 200:
                    link_token = response.json()["link_token"]
                    
                    # Plaid Link component
                    plaid_link_html = f"""
                    <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
                    <script>
                    // Why this exists: Plaid Link is a pre-built widget that handles
                    // the complex OAuth flows for thousands of banks
                    
                    const handler = Plaid.create({{
                        token: '{link_token}',
                        onSuccess: (public_token, metadata) => {{
                            // Send token to parent
                            window.parent.postMessage({{
                                type: 'plaid_success',
                                public_token: public_token,
                                institution: metadata.institution
                            }}, '*');
                        }},
                        onLoad: () => {{}},
                        onExit: (err, metadata) => {{
                            window.parent.postMessage({{
                                type: 'plaid_exit'
                            }}, '*');
                        }},
                        onEvent: (eventName, metadata) => {{}}
                    }});
                    
                    handler.open();
                    </script>
                    """
                    
                    # Render Plaid Link
                    components.html(plaid_link_html, height=500)
                    
                    # Listen for messages from Plaid Link
                    st.info("🔒 Plaid Link opened in a secure window...")
                    
                else:
                    st.error("Failed to initialize connection")
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