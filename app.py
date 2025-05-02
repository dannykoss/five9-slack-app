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

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "Authorization": f"Basic {auth}"
    }

    # Step 1: Set session
    session_body = """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.supervisor.ws.five9.com/">
       <soapenv:Header/>
       <soapenv:Body>
          <ser:setSessionParameters>
             <viewSettings>
                <forceLogoutSession>true</forceLogoutSession>
                <rollingPeriod>Minutes30</rollingPeriod>
                <shiftStart>28800000</shiftStart>
                <statisticsRange>CurrentWeek</statisticsRange>
                <timeZone>-25200000</timeZone>
             </viewSettings>
          </ser:setSessionParameters>
       </soapenv:Body>
    </soapenv:Envelope>
    """

    response1 = requests.post(
        "https://api.five9.com/wssupervisor/SupervisorWebService",
        data=session_body,
        headers=headers,
        timeout=10
    )

    if "Fault" in response1.text:
        return jsonify({
            "response_type": "ephemeral",
            "text": "Failed to set session. Cannot continue."
        })

    # Step 2: Get statistics
    stats_body = """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.supervisor.ws.five9.com/">
       <soapenv:Header/>
       <soapenv:Body>
          <ser:getStatistics>
             <statisticType>AgentStatistics</statisticType>
          </ser:getStatistics>
       </soapenv:Body>
    </soapenv:Envelope>
    """

    response2 = requests.post(
        "https://api.five9.com/wssupervisor/SupervisorWebService",
        data=stats_body,
        headers=headers,
        timeout=10
    )

    # Try to parse at least some output
    root = ET.fromstring(response2.text)
    rows = []
    for row in root.iter():
        if row.tag.endswith('values'):
            values = [v.text for v in row if v.tag.endswith('data')]
            if values:
                rows.append(values)

    if rows:
        text = "*Five9 Agent Stats:*\n"
        for row in rows:
            text += " • " + " | ".join(row) + "\n"
    else:
        text = "No usable data found."

    return jsonify({
        "response_type": "in_channel",
        "text": text
    })
