import os
import base64
import requests
import threading
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify

app = Flask(__name__)


def format_time(time_str):
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
        return time_str

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
        "[Default]", "Training", "Five9 - Test Only", "Skill Name",
        "Zipcar - Internal Support", "CCI - Fleet"
    ]

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
    requests.post("https://api.five9.com/wssupervisor/SupervisorWebService", data=session_body, headers=headers, timeout=10)

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

    res = requests.post("https://api.five9.com/wssupervisor/SupervisorWebService", data=stats_body, headers=headers, timeout=10)
    root = ET.fromstring(res.text)
    rows = [
        [v.text if v.text is not None else "" for v in row if v.tag.endswith('data')]
        for row in root.iter() if row.tag.endswith('values')
    ]

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*\ud83d\udcca Five9 Queue Stats*"}},
        {"type": "divider"}
    ]

    for row in rows:
        if row[0] == "Skill Name" or "Agents Logged In" in row:
            continue

        skill = row[0]
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
            service_level = f"{round(sl_val * 100)}%" if sl_val <= 1 else f"{round(sl_val)}%"
        except:
            service_level = f"{service_level}%"

        block_text = (
            f"*{skill}*\n"
            f"\u2022 \ud83d\udc65 Agents On Call: {on_call}\n"
            f"\u2022 \u26d4 Agents Not Ready: {not_ready}\n"
            f"\u2022 \ud83d\udfe2 Agents Ready: {ready}\n"
            f"\u2022 \u260e\ufe0f Calls in Queue: {calls_in_queue}\n"
            f"\u2022 \ud83d\udd01 Queue Callbacks: {queue_callbacks}\n"
            f"\u2022 \ud83d\udd52 Longest Wait: {longest_wait_time}\n"
            f"\u2022 \ud83d\udcc8 Service Level: {service_level}"
        )

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": block_text}})

    # Fetch campaign statistics
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

    campaign_res = requests.post("https://api.five9.com/wssupervisor/SupervisorWebService", data=campaign_body, headers=headers, timeout=10)
    campaign_root = ET.fromstring(campaign_res.text)
    campaign_rows = [
        [v.text if v.text is not None else "" for v in row if v.tag.endswith('data')]
        for row in campaign_root.iter() if row.tag.endswith('values')
    ]

    if campaign_rows:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*\ud83d\udcde Campaign Performance Stats*"}})

        for row in campaign_rows:
            print(f"DEBUG - Campaign: {row[0] if len(row) > 0 else 'N/A'} - Full Row: {row}")  # 👈 Place it here

            campaign = row[0] if len(row) > 0 else "N/A"
            if campaign != "Zipcar Inbound - 866-4ZIPCAR":
                continue

            asa = format_time(row[5]) if len(row) > 5 else "?"
            aht = format_time(row[6]) if len(row) > 6 else "?"
            abandon_rate = row[7] if len(row) > 7 else "?"
            service_level = row[9] if len(row) > 9 else "?"

            try:
                sl_val = float(service_level)
                service_level = f"{round(sl_val * 100)}%" if sl_val <= 1 else f"{round(sl_val)}%"
            except:
                service_level = f"{service_level}%"

            try:
                ar_val = float(abandon_rate)
                abandon_rate = f"{round(ar_val * 100)}%" if ar_val <= 1 else f"{round(ar_val)}%"
            except:
                abandon_rate = f"{abandon_rate}%"

            block_text = (
                f"*\ud83d\udcbc {campaign}*\n"
                f"\u2022 \u23f3 ASA: {asa}\n"
                f"\u2022 \u231b AHT: {aht}\n"
                f"\u2022 \ud83d\udeab Abandon Rate: {abandon_rate}\n"
                f"\u2022 \ud83d\udcc8 Service Level: {service_level}"
            )

            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": block_text}})

    if not rows and not campaign_rows:
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "\u26a0\ufe0f No queue or campaign stats available at the moment."}}]

    requests.post(response_url, json={"response_type": "in_channel", "blocks": blocks})


@app.route("/queue-stats", methods=["POST"])
def queue_stats():
    response_url = request.form.get("response_url")
    username = os.environ.get("FIVE9_USERNAME")
    password = os.environ.get("FIVE9_PASSWORD")

    threading.Thread(target=fetch_stats_and_respond, args=(response_url, username, password)).start()

    return jsonify({
        "response_type": "ephemeral",
        "text": "\ud83d\udd04 Fetching Five9 queue and campaign stats\u2026 please wait."
    })
