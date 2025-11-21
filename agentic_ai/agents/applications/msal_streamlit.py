import streamlit as st  
import msal  
import os  
  
def login() -> str:  
    """  
    Login the user via MSAL device code flow and return the access token  
    issued for the frontend app (so it contains the frontend's roles).  
    """  
  
    # Frontend App Registration ID  
    client_id = os.getenv("CLIENT_ID") or os.getenv("AZURE_AD_CLIENT_ID")  
    if not client_id:  
        raise RuntimeError("CLIENT_ID (frontend app registration) must be set")  
  
    # Multi-tenant authority (common) so users from any tenant can sign in  
    authority = os.getenv("AUTHORITY") or "https://login.microsoftonline.com/common/v2.0"  
  
    # Request the default scope for *this frontend app* so that roles from this app are in the token  
    scopes = [f"{client_id}/.default"]    
    cache = msal.SerializableTokenCache()  
    app = msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)  
  
    accounts = app.get_accounts()  
    if accounts:  
        result = app.acquire_token_silent(scopes, account=accounts[0])  
        if result and "access_token" in result:  
            return result["access_token"]  
  
    # Device code flow for Streamlit  
    flow = app.initiate_device_flow(scopes=scopes)  
    if "user_code" not in flow:  
        raise RuntimeError("Failed to create device flow")  
      
    st.info(f"Use code {flow['user_code']} at {flow['verification_uri']} to sign in")  
    result = app.acquire_token_by_device_flow(flow)  
    if not result or "access_token" not in result:  
        raise RuntimeError(result.get("error_description", "Login failed"))  
  
    return result["access_token"]  