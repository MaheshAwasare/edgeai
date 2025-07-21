import streamlit as st
import time
import logging
import io
from atc_logic import ATCMessageProcessor

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="ATC Message Classifier",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f4e79;
        margin-bottom: 30px;
    }
    .success-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 10px 0;
    }
    .error-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        margin: 10px 0;
    }
    .info-box {
        padding: 15px;
        border-radius: 8px;
        background-color: #e7f3ff;
        border: 1px solid #b3d9ff;
        margin: 10px 0;
    }
    .classification-result {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #007bff;
        margin: 15px 0;
    }
    .response-box {
        background-color: #fff3cd;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ffc107;
        margin: 15px 0;
    }
    .indicator-container {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        padding: 20px;
        background-color: #f8f9fa;
        border-radius: 10px;
    }
    .indicator {
        display: flex;
        align-items: center;
        padding: 8px 15px;
        border-radius: 20px;
        font-weight: bold;
        transition: all 0.3s ease;
        border: 2px solid #d1d1d1;
        color: #6c757d;
        background-color: #e9ecef;
    }
    .indicator.on {
        color: #fff;
        background-color: #28a745;
        border-color: #28a745;
        box-shadow: 0 0 10px #28a745;
    }
    .indicator.emergency.on {
        background-color: #dc3545;
        border-color: #dc3545;
        box-shadow: 0 0 15px #dc3545;
    }
</style>
""", unsafe_allow_html=True)


def create_indicator_display(message_type):
    """Create a display of indicators for message types."""
    st.markdown("<h4>Message Type Indicators</h4>", unsafe_allow_html=True)

    indicators = {
        "EMERGENCY": "🚨 Emergency",
        "TRAFFIC": "🚦 Traffic",
        "FUEL": "⛽ Fuel",
        "RUNWAY": "✈️ Runway",
        "TAXI": "🚕 Taxi",
        "TAKEOFF": "🛫 Takeoff",
        "LANDING": "🛬 Landing"
    }

    # Normalize message_type to uppercase for reliable matching
    normalized_message_type = message_type.upper()

    html_content = "<div class='indicator-container'>"
    for key, label in indicators.items():
        # Check if the key is a substring of the normalized message type
        status_class = "on" if key in normalized_message_type else ""
        if key == "EMERGENCY" and "EMERGENCY" in normalized_message_type:
            status_class += " emergency"
        html_content += f"<div class='indicator {status_class}'>{label}</div>"
    html_content += "</div>"

    st.markdown(html_content, unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if 'processor' not in st.session_state:
        st.session_state.processor = None
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
    if 'connection_status' not in st.session_state:
        st.session_state.connection_status = None
    if 'sender_type' not in st.session_state:
        st.session_state.sender_type = "AUTO"


def create_sidebar():
    """Create and populate the sidebar."""
    st.sidebar.title("⚙️ Configuration")

    # Ollama Configuration
    st.sidebar.subheader("Ollama Settings")
    ollama_url = st.sidebar.text_input(
        "Ollama API URL",
        value="http://127.0.0.1:11434/api/chat",
        help="URL of your Ollama API endpoint"
    )

    ollama_model = st.sidebar.text_input(
        "Model Name",
        value="gemma3:4b",
        help="Name of the Ollama model to use"
    )

    # Test connection button
    if st.sidebar.button("🔗 Test Connection"):
        with st.spinner("Testing connection..."):
            processor = ATCMessageProcessor(ollama_url, ollama_model)
            connection_result = processor.validate_connection()
            st.session_state.connection_status = connection_result

            if connection_result["success"]:
                st.sidebar.success("✅ " + connection_result["message"])
                st.session_state.processor = processor
            else:
                st.sidebar.error("❌ " + connection_result["message"])

    # Display connection status
    if st.session_state.connection_status:
        if st.session_state.connection_status["success"]:
            st.sidebar.success("Status: Connected")
        else:
            st.sidebar.error("Status: Disconnected")

    st.sidebar.markdown("---")

    # Example messages
    st.sidebar.subheader("📝 Example Messages")
    if st.session_state.processor:
        examples = st.session_state.processor.get_message_examples()

        selected_example = st.sidebar.selectbox(
            "Choose an example:",
            ["Select an example..."] + list(examples.keys())
        )

        if selected_example != "Select an example...":
            example_data = examples[selected_example]
            st.sidebar.text_area(
                "Example Message:",
                value=example_data["message"],
                height=100,
                disabled=True
            )
            st.sidebar.info(f"**Sender:** {example_data['sender']}")

            if st.sidebar.button("📋 Use This Example"):
                st.session_state.example_message = example_data["message"]
                st.session_state.example_sender = example_data["sender"]

    return ollama_url, ollama_model


def display_classification_results(result_data):
    """Display the classification results in a formatted way."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="classification-result">
            <h4>📊 Classification Details</h4>
        </div>
        """, unsafe_allow_html=True)

        # Create metrics
        sender = result_data.get("sender", "Unknown")
        message_type = result_data.get("type", "Unknown")
        aircraft = result_data.get("aircraft", "Not specified")

        st.metric("Message Sender", sender)
        st.metric("Message Type", message_type)
        st.metric("Aircraft", aircraft)

        # Details
        st.subheader("Details")
        st.write(result_data.get("details", "No details available"))

    with col2:
        # Determine response type based on sender
        sender = result_data.get("sender", "Unknown").upper()
        if sender == "PILOT":
            response_title = "📡 ATC Response"
            response_help = "Appropriate Air Traffic Control response to pilot message"
        elif sender == "ATC":
            response_title = "✈️ Pilot Response"
            response_help = "Appropriate pilot response to ATC message"
        else:
            response_title = "📞 Recommended Response"
            response_help = "Appropriate response based on message analysis"

        st.markdown(f"""
        <div class="response-box">
            <h4>{response_title}</h4>
        </div>
        """, unsafe_allow_html=True)

        response_text = result_data.get("response", "No response generated")
        st.text_area(
            f"Response:",
            value=response_text,
            height=200,
            help=response_help
        )


def main():
    """Main application function."""
    initialize_session_state()

    # Header
    st.markdown("""
    <h1 class="main-header">✈️ ATC Message Classifier & Response Generator</h1>
    <p style="text-align: center; color: #666; margin-bottom: 40px;">
        Classify aviation communications and generate appropriate pilot/ATC responses using AI
    </p>
    """, unsafe_allow_html=True)

    # Sidebar
    ollama_url, ollama_model = create_sidebar()

    # Initialize processor if not already done
    if not st.session_state.processor:
        st.session_state.processor = ATCMessageProcessor(ollama_url, ollama_model)

    # Main input section
    st.subheader("🎙️ Enter ATC Message")

    # Sender type selection
    col1, col2 = st.columns([2, 1])
    with col1:
        # Check if example sender should be used
        default_message = ""
        if hasattr(st.session_state, 'example_message'):
            default_message = st.session_state.example_message
            delattr(st.session_state, 'example_message')

        user_message = st.text_area(
            "Type or paste the ATC message here:",
            value=default_message,
            height=120,
            placeholder="Example: Tower, American 567 requesting taxi to runway 09R for departure",
            help="Enter any ATC communication message for classification and response generation"
        )

    with col2:
        st.markdown("**Message Sender:**")

        # Check if example sender should be used
        default_sender_index = 0
        if hasattr(st.session_state, 'example_sender'):
            example_sender = st.session_state.example_sender
            if example_sender == "PILOT":
                default_sender_index = 1
            elif example_sender == "ATC":
                default_sender_index = 2
            delattr(st.session_state, 'example_sender')

        sender_option = st.radio(
            "Select message sender:",
            options=["🤖 Auto-detect", "✈️ From Pilot", "🏢 From ATC"],
            index=default_sender_index,
            help="Choose who is sending the message to generate appropriate response"
        )

        # Map radio selection to sender type
        sender_mapping = {
            "🤖 Auto-detect": "AUTO",
            "✈️ From Pilot": "PILOT",
            "🏢 From ATC": "ATC"
        }
        sender_type = sender_mapping[sender_option]

        # Show expected response type
        if sender_type == "PILOT":
            st.info("📡 **Response:** ATC will respond")
        elif sender_type == "ATC":
            st.info("✈️ **Response:** Pilot will respond")
        else:
            st.info("🔍 **Response:** Auto-determined")

    # Classification button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        classify_button = st.button(
            "🔍 Process",
            type="primary",
            use_container_width=True,
            disabled=not user_message.strip() or not st.session_state.processor
        )

    # Process message if button clicked
    if classify_button and user_message.strip():
        # Set up a custom handler to capture logs
        log_capture_string = io.StringIO()
        ch = logging.StreamHandler(log_capture_string)
        ch.setLevel(logging.INFO)

        # Add the handler to the logger
        logger = logging.getLogger()
        logger.addHandler(ch)

        if not st.session_state.connection_status or not st.session_state.connection_status["success"]:
            st.warning("⚠️ Please test the connection first using the sidebar.")
            logger.warning("Connection not established")
            return

        with st.spinner("🤖 Analyzing message..."):
            progress_bar = st.progress(0)
            st.session_state.processor = ATCMessageProcessor(ollama_url, ollama_model)

            for i in range(20):
                time.sleep(0.05)
                progress_bar.progress((i + 1) * 5)

            try:
                result = st.session_state.processor.classify_message(user_message, sender_type)
                st.session_state.last_result = result

            except Exception as e:
                logger.error(f"Exception during classification: {str(e)}")
                st.error(f"❌ Exception occurred: {str(e)}")
                st.session_state.last_result = {
                    "success": False,
                    "error": f"Exception: {str(e)}",
                    "data": {}
                }

            for i in range(20, 100):
                time.sleep(0.01)
                progress_bar.progress(i + 1)

            progress_bar.empty()

        # Remove the handler
        logger.removeHandler(ch)

        # Get the captured logs
        log_contents = log_capture_string.getvalue()
        st.session_state.last_log = log_contents

    # Display results
    if st.session_state.last_result:
        result = st.session_state.last_result

        st.markdown("---")
        st.subheader("📊 Results")

        if result["success"]:
            st.success("✅ Message classified successfully!")
            display_classification_results(result["data"])

            with st.expander("📊 View Message Indicators", expanded=True):
                create_indicator_display(result["data"].get("type", ""))

            # Show raw response in expander
            with st.expander("🔍 View Raw AI Response"):
                st.text(result.get("raw_response", "No raw response available"))

        else:
            st.error(f"❌ Error: {result.get('error', 'Unknown error occurred')}")

        # Display processing details in a collapsible section
        if st.session_state.last_log:
            st.markdown("---")
            with st.expander("⚙️ View Processing Details"):
                st.code(st.session_state.last_log)

    # Information section
    st.markdown("---")

    # Log viewer
    with st.expander("📋 Console Logs (for debugging)"):
        st.markdown("**Check your terminal/console for detailed logs**")
        st.code("""
# To see logs, run the app from terminal:
streamlit run app.py

# Logs will show:
# - Connection attempts
# - API calls to Ollama
# - Response parsing
# - Error details
        """)

    with st.expander("ℹ️ How to Use This App"):
        st.markdown("""
        ### Instructions:
        1. **Configure Ollama**: Make sure Ollama is running locally with the specified model
        2. **Test Connection**: Use the sidebar to test your Ollama connection
        3. **Enter Message**: Type or paste any ATC communication message
        4. **Classify**: Click the classify button to analyze the message
        5. **Review Results**: View the classification and recommended response

        ### Message Types:
        - **EMERGENCY**: Mayday calls, urgent situations
        - **NORMAL**: Routine communications
        - **WEATHER**: Weather-related requests
        - **TRAFFIC**: Traffic advisories and alerts
        - **NAVIGATION**: Course changes, vectors
        - **FUEL**: Fuel-related communications
        - **RUNWAY**: Runway operations
        - **COMMUNICATION**: Radio checks, frequency changes

        ### Example Messages:
        Use the sidebar to select from various example messages to test the system.
        """)


if __name__ == "__main__":
    main()