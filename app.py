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
               <statisticType>ACDStatus</statisticType>
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
        rows = []
        for row in root.iter():
            if row.tag.endswith('values'):
                values = [v.text for v in row if v.tag.endswith('data')]
                if values:
                    rows.append(values)

        if rows:
            text = "*Five9 Queue Stats:*\n"
            for row in rows:
                text += " • " + " | ".join(row) + "\n"
        else:
            text = "No usable rows found in the response."


    except Exception as e:
        text = f"Error contacting Five9: {str(e)}"

    return jsonify({
        "response_type": "in_channel",
        "text": text
    })
