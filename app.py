import os
import base64
import requests
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/queue-stats", methods=["POST"])
def queue_stats():
    username = os.environ.get("FIVE9_USERNAME")
    password = os.environ.get("FIVE9_PASSWORD")
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()

    soap_body = f"""
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.supervisor.ws.five9.com/">
       <soapenv:Header/>
       <soapenv:Body>
          <ser:getStatistics>
             <statisticType>AgentStatistics</statisticType>
          </ser:getStatistics>
       </soapenv:Body>
    </soapenv:Envelope>
    """

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "Authorization": f"Basic {auth}"
    }

    try:
        response = requests.post(
            "https://api.five9.com/wssupervisor/SupervisorWebService",
            data=soap_body,
            headers=headers,
            timeout=10
        )

        # Return the raw response XML to Slack (trimmed to 3000 characters)
        raw = response.text.strip().replace("\n", "").replace("  ", "")
        if len(raw) > 2900:
            raw = raw[:2900] + "..."

        return jsonify({
            "response_type": "ephemeral",
            "text": f"```\n{raw}\n```"
        })

    except Exception as e:
        return jsonify({
            "response_type": "ephemeral",
            "text": f"Error: {str(e)}"
        })
