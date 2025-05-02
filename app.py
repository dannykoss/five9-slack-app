import os
import base64
import requests
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/queue-stats", methods=["POST"])
def queue_stats():
    slack_token = request.form.get("token")

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
        root = ET.fromstring(response.text)

        # Pull the first two <data> elements for demo purposes
        data_values = [elem.text for elem in root.iter() if elem.tag.endswith('data')]
        if len(data_values) >= 2:
            skill = data_values[0]
            calls_in_queue = data_values[1]
            text = f"*Skill:* {skill}\n*Calls in Queue:* {calls_in_queue}"
        else:
            text = "No data found."

    except Exception as e:
        text = f"Error contacting Five9: {str(e)}"

    return jsonify({
        "response_type": "in_channel",
        "text": text
    })
