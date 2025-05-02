import threading
from flask import Flask, request, jsonify
import requests
import os
import base64
import xml.etree.ElementTree as ET

app = Flask(__name__)

def fetch_stats_and_respond(response_url, username, password):
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
    requests.post(
        "https://api.five9.com/wssupervisor/SupervisorWebService",
        data=session_body,
        headers=headers,
        timeout=10
    )

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

    res = requests.post(
        "https://api.five9.com/wssupervisor/SupervisorWebService",
        data=stats_body,
        headers=headers,
        timeout=10
    )

    root = ET.fromstring(res.text)
    rows = []
    for row in root.iter():
        if row.tag.endswith('values'):
            values = [v.text if v.text is not None else "" for v in row if v.tag.endswith('data')]
            if values:
                rows.append(values)

    if rows:
        text = "*Five9 Agent Stats:*\n"
        for row in rows:
            text += " • " + " | ".join(row) + "\n"
    else:
        text = "No data available."

    # Send follow-up to Slack
    requests.post(response_url, json={
        "response_type": "in_channel",
        "text": text
    })

@app.route("/queue-stats", methods=["POST"])
def queue_stats():
    response_url = request.form.get("response_url")
    username = os.environ.get("FIVE9_USERNAME")
    password = os.environ.get("FIVE9_PASSWORD")

    # Do the long-running work in a background thread
    threading.Thread(target=fetch_stats_and_respond, args=(response_url, username, password)).start()

    # Respond quickly to Slack
    return jsonify({
        "response_type": "ephemeral",
        "text": "🔄 Fetching Five9 stats... please wait a moment."
    })
