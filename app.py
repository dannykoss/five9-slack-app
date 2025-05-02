import os
import base64
import requests
import threading
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify

app = Flask(__name__)


def format_time(time_str):
    """Convert HH:MM:SS or MM:SS to XmYs format"""
    if not time_str or time_str == "00:00:00":
        return "0m0s"
    parts = time_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        total_seconds = hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes, seconds = map(int, parts)
        total_seconds = minutes * 60 + seconds
    else:
        return time_str  # fallback

    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}m{seconds}s"


def fetch_stats_and_respond(response_url, username, password):
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "Authorization": f"Basic {auth}"
    }

    excluded_skills = [
    "[Default]",
    "Training",
    "Five9 - Test Only",
    "Skill Name",
    "Zipcar - Internal Support",
    "CCI - Fleet"
]

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

    # Step 2: Get ACDStatus stats
    stats_body = """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.supervisor.ws.five9.com/">
       <soapenv:Header/>
       <soapenv:Body>
          <ser:getStatistics>
             <statisticType>ACDStatus</statisticType>
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

    campaign_body = """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.supervisor.ws.five9.com/">
       <soapenv:Header/>
       <soapenv:Body>
          <ser:getStatistics>
             <statisticType>CampaignState</statisticType>
          </ser:getStatistics>
       </soapenv:Body>
    </soapenv:Envelope>
    """

    campaign_res = requests.post(
        "https://api.five9.com/wssupervisor/SupervisorWebService",
        data=campaign_body,
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

    campaign_root = ET.fromstring(campaign_res.text)
    campaign_rows = []
    for row in campaign_root.iter():
        if row.tag.endswith("values"):
            values = [v.text if v.text is not None else "" for v in row if v.tag.endswith("data")]
            if values:
                campaign_rows.append(values)

    
    if rows:
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*📊 Five9 Queue Stats*"}
            },
        ]

        for row in rows:
            print(f"DEBUG - Skill: {row[0] if len(row) > 0 else 'N/A'} - Full Row: {row}")
            skill = row[0] if len(row) > 0 else "N/A"
            if skill in excluded_skills:
                continue
            on_call = row[3] if len(row) > 3 else "?"
            not_ready = row[2] if len(row) > 2 else "?"
            ready = row[4] if len(row) > 4 else "?"
            calls_in_queue = row[6] if len(row) > 6 else "?"
            queue_callbacks = row[10] if len(row) > 10 else "?"
            longest_wait_time = format_time(row[8]) if len(row) > 8 else "?"
            service_level = row[11] if len(row) > 11 else "?"

            try:
                sl_val = float(service_level)
                if sl_val <= 1:
                    service_level = f"{round(sl_val * 100)}%"
                else:
                    service_level = f"{round(sl_val)}%"
            except:
                service_level = f"{service_level}%"


            block_text = (
                f"*{skill}*\n"
                f"• 👥 Agents On Call: {on_call}\n"
                f"• ⛔ Agents Not Ready: {not_ready}\n"
                f"• 🟢 Agents Ready: {ready}\n"
                f"• ☎️ Calls in Queue: {calls_in_queue}\n"
                f"• 🔁 Queue Callbacks: {queue_callbacks}\n"
                f"• 🕒 Longest Wait: {longest_wait_time}\n"
                f"• 📈 Service Level: {service_level}"
            )

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": block_text}
            })
    else:
        blocks = [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "⚠️ No queue stats available at the moment."}
        }]

    # Send message to Slack
    requests.post(response_url, json={
        "response_type": "in_channel",
        "blocks": blocks
    })

    if campaign_rows:
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*📞 Campaign Performance Stats*"}
    })

    for row in campaign_rows:
        campaign = row[0] if len(row) > 0 else "N/A"
        asa = row[5] if len(row) > 5 else "?"
        aht = row[6] if len(row) > 6 else "?"
        service_level = row[9] if len(row) > 9 else "?"
        abandon_rate = row[7] if len(row) > 7 else "?"

        try:
            service_level = f"{round(float(service_level) * 100)}%" if float(service_level) <= 1 else f"{round(float(service_level))}%"
        except:
            service_level = f"{service_level}%"

        try:
            abandon_rate = f"{round(float(abandon_rate) * 100)}%" if float(abandon_rate) <= 1 else f"{round(float(abandon_rate))}%"
        except:
            abandon_rate = f"{abandon_rate}%"

        block_text = (
            f"*{campaign}*\n"
            f"• ⏳ ASA: {asa}\n"
            f"• ⌛ AHT: {aht}\n"
            f"• 📈 Service Level: {service_level}\n"
            f"• 🚫 Abandon Rate: {abandon_rate}"
        )

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": block_text}
        })



@app.route("/queue-stats", methods=["POST"])
def queue_stats():
    response_url = request.form.get("response_url")
    username = os.environ.get("FIVE9_USERNAME")
    password = os.environ.get("FIVE9_PASSWORD")

    # Start the background job to avoid Slack timeout
    threading.Thread(target=fetch_stats_and_respond, args=(response_url, username, password)).start()

    # Immediate response to Slack
    return jsonify({
        "response_type": "ephemeral",
        "text": "🔄 Fetching Five9 queue stats… please wait."
    })
