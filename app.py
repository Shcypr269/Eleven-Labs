"""CallPilot - Voice AI Appointment Scheduler (Streamlit UI)"""
import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="CallPilot", page_icon="📞", layout="wide")

st.title("📞 CallPilot - Voice AI Appointment Scheduler")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("Navigation")
    page = st.radio("Go to", ["🏠 Home", "🔍 Search Providers", "📅 Book Appointment", "🐝 Swarm Mode", "📞 Voice Call"])
    
    st.markdown("---")
    twilio_status = "✅ Connected" if st.session_state.get("twilio_connected") else "❌ Not Connected"
    elevenlabs_status = "✅ Connected" if st.session_state.get("api_key") else "❌ Not Set"
    st.info(f"**Twilio:** {twilio_status}  |  **ElevenLabs:** {elevenlabs_status}")
    if not st.session_state.get("api_key"):
        api_key = st.text_input("ElevenLabs API Key", type="password")
        if api_key:
            st.session_state.api_key = api_key
            st.success("API Key saved!")

# Home Page
if page == "🏠 Home":
    # Check Twilio connection
    try:
        response = requests.get(f"{BASE_URL}/calls/history")
        if response.status_code == 200:
            st.session_state.twilio_connected = True
    except:
        st.session_state.twilio_connected = False
    
    st.header("Welcome to CallPilot!")
    st.markdown("""
    ### Features:
    - 🔍 **Search Providers** - Find doctors, dentists, hospitals near you
    - 📅 **Book Appointment** - Schedule appointments with AI assistance
    - 🐝 **Swarm Mode** - Call multiple providers simultaneously
    - 📞 **Voice Call** - AI-powered voice calls using ElevenLabs
    
    ### How it works:
    1. Search for healthcare providers in your area
    2. Rank providers based on ratings, distance, and price
    3. Book appointments automatically with AI voice calls
    4. Get real-time updates on booking status
    """)
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Providers", "4+")
    with col2:
        st.metric("Coverage", "Bhubaneswar")
    with col3:
        st.metric("Avg. Rating", "4.5⭐")
    with col4:
        st.metric("Status", "Online")

# Search Providers
elif page == "🔍 Search Providers":
    st.header("🔍 Search Healthcare Providers")
    
    col1, col2 = st.columns(2)
    with col1:
        service_type = st.selectbox("Service Type", ["hospital", "dentist", "doctor", "clinic", "pharmacy"])
    with col2:
        location = st.text_input("Location", "KIIT Bhubaneswar")
    
    if st.button("🔍 Search", type="primary"):
        with st.spinner("Searching providers..."):
            try:
                response = requests.get(f"{BASE_URL}/places/search", params={"service_type": service_type, "location": location})
                if response.status_code == 200:
                    data = response.json()
                    providers = data.get("providers", [])
                    
                    if providers:
                        st.success(f"Found {data['count']} providers!")
                        for i, p in enumerate(providers, 1):
                            with st.expander(f"#{i} {p['name']} - ⭐ {p['rating']}", expanded=(i==1)):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**📍 Distance:** {p['distance_miles']} miles")
                                    st.write(f"**💰 Price:** ₹{p['price_range']}")
                                    st.write(f"**📞 Phone:** {p['phone']}")
                                with col2:
                                    st.write(f"**⏰ Availability:** {', '.join(p['availability'])}")
                                    st.write(f"**🗺️ Location:** {p['lat']}, {p['lon']}")
                                st.write(f"**📬 Address:** {p['address']}")
                    else:
                        st.warning("No providers found. Try a different location.")
                else:
                    st.error(f"Error: {response.status_code}")
            except Exception as e:
                st.error(f"Failed to connect to server: {e}")
                st.info("Make sure the FastAPI server is running on port 8000")

# Book Appointment
elif page == "📅 Book Appointment":
    st.header("📅 Book an Appointment")
    
    with st.form("booking_form"):
        col1, col2 = st.columns(2)
        with col1:
            service_type = st.selectbox("Service Type", ["dentist", "doctor", "hospital", "plumber", "electrician"])
            user_name = st.text_input("Your Name", "User")
        with col2:
            location = st.text_input("Location", "KIIT Bhubaneswar")
            time_preference = st.selectbox("Time Preference", ["morning", "afternoon", "evening"])
        
        max_budget = st.slider("Max Budget (₹)", 500, 5000, 2000, step=100)
        
        submitted = st.form_submit_button("📅 Find & Book", type="primary")
        
        if submitted:
            with st.spinner("Finding best providers and checking availability..."):
                try:
                    response = requests.post(f"{BASE_URL}/book", json={
                        "service_type": service_type,
                        "location": location,
                        "time_preference": time_preference,
                        "max_budget": max_budget,
                        "user_name": user_name
                    })
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            st.success("✅ Appointment Found!")
                            st.json(result)
                        else:
                            st.warning(f"⚠️ {result.get('message', 'No slots available')}")
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Failed: {e}")

# Swarm Mode
elif page == "🐝 Swarm Mode":
    st.header("🐝 Swarm Calling Mode")
    st.markdown("Call multiple providers simultaneously to find the best appointment")
    
    with st.form("swarm_form"):
        col1, col2 = st.columns(2)
        with col1:
            service_type = st.selectbox("Service Type", ["dentist", "doctor", "hospital"])
            location = st.text_input("Location", "KIIT Bhubaneswar")
        with col2:
            time_preference = st.selectbox("Time Preference", ["morning", "afternoon", "evening"])
            max_providers = st.slider("Max Providers to Call", 1, 10, 5)
        
        submitted = st.form_submit_button("🐝 Start Swarm Campaign", type="primary")
        
        if submitted:
            with st.spinner("Starting swarm campaign..."):
                try:
                    response = requests.post(f"{BASE_URL}/swarm", json={
                        "service_type": service_type,
                        "location": location,
                        "time_preference": time_preference,
                        "max_providers": max_providers
                    })
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Swarm Campaign Started!")
                        st.session_state.campaign_id = result.get("campaign_id")
                        st.json(result)
                        
                        # Auto-refresh status
                        st.info("Campaign ID saved. Go to 'Swarm Status' to check progress.")
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Failed: {e}")
    
    # Check status if campaign exists
    if st.session_state.get("campaign_id"):
        st.subheader("📊 Campaign Status")
        if st.button("🔄 Refresh Status"):
            try:
                cid = st.session_state.campaign_id
                response = requests.get(f"{BASE_URL}/swarm/{cid}")
                if response.status_code == 200:
                    status = response.json()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Status", status.get("status", "unknown"))
                    with col2:
                        st.metric("Success Rate", f"{status.get('success_rate', 0)*100:.0f}%")
                    with col3:
                        st.metric("Calls Made", status.get("calls_made", 0))
                    st.json(status)
            except Exception as e:
                st.error(f"Failed to get status: {e}")

# Voice Call
elif page == "📞 Voice Call":
    st.header("📞 AI Voice Call")
    st.markdown("Make an AI-powered voice call to a provider using Twilio & ElevenLabs")
    
    # Show connection status
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Twilio Status", "✅ Connected" if st.session_state.get("twilio_connected") else "❌ Not Connected")
    with col2:
        st.metric("ElevenLabs Status", "✅ Connected" if st.session_state.get("api_key") else "❌ Not Set")
    
    with st.form("voice_call_form"):
        col1, col2 = st.columns(2)
        with col1:
            provider_name = st.text_input("Provider Name", "KIIT Hospital")
            service_type = st.selectbox("Service Type", ["hospital", "dentist", "doctor"])
        with col2:
            provider_phone = st.text_input("Provider Phone", "+91-674-2725500")
            user_name = st.text_input("Your Name", "User")
        
        call_type = st.radio("Call Type", ["🤖 AI Voice Call (Mock)", "📞 Real Twilio Call"], horizontal=True)
        
        submitted = st.form_submit_button("📞 Initiate Call", type="primary", disabled=not st.session_state.get("twilio_connected"))
        
        if submitted:
            if call_type == "📞 Real Twilio Call":
                with st.spinner("📞 Placing call via Twilio..."):
                    try:
                        response = requests.post(f"{BASE_URL}/voice/call", params={
                            "provider_phone": provider_phone,
                            "provider_name": provider_name,
                            "service_type": service_type,
                            "user_name": user_name
                        })
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success("✅ Call Initiated!")
                            st.json(result)
                            
                            # Show call history
                            st.subheader("📋 Recent Calls")
                            history_resp = requests.get(f"{BASE_URL}/calls/history")
                            if history_resp.status_code == 200:
                                history = history_resp.json().get("calls", [])
                                if history:
                                    for call in history:
                                        status_color = "🟢" if call.get("status") in ["completed", "in-progress"] else "🔴"
                                        st.write(f"{status_color} {call.get('name', 'Unknown')} - {call.get('phone', '')} ({call.get('status', 'unknown')})")
                        else:
                            st.error(f"Error: {response.status_code}")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            else:
                with st.spinner("🤖 AI Agent is calling (mock mode)..."):
                    try:
                        response = requests.post(f"{BASE_URL}/voice/call", params={
                            "provider_phone": provider_phone,
                            "provider_name": provider_name,
                            "service_type": service_type,
                            "user_name": user_name
                        })
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success("✅ Call Completed (Mock)!")
                            st.json(result)
                    except Exception as e:
                        st.error(f"Failed: {e}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>CallPilot v1.0.0 | Powered by ElevenLabs Voice AI & OpenStreetMap</p>
</div>
""", unsafe_allow_html=True)
