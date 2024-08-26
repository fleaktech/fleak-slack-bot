import json
import os

import requests
from slack_sdk import WebClient


def lambda_handler(event, context):
    print(f"received request: {json.dumps(event)}")

    headers = event.get('headers', {})

    # Check if this is a retry
    if 'x-slack-retry-num' in headers:
        retry_num = headers.get('x-slack-retry-num')
        print(f"Retry number: {retry_num}")
        return {"statusCode": 200, "body": "Retry received"}

    if 'body' not in event:
        return event
    try:
        body = json.loads(event['body'])
    except:
        return {
            'error': 'cannot parse event body',
            'body': event['body']
        }

    if 'type' in body and body["type"] == "url_verification":
        return {"challenge": body["challenge"]}

    url = os.environ['FLEAK_API_URL']
    headers = {
        "api-key": os.environ["FLEAK_API_KEY"],
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=[body])
    answer = response.json()['outputEvents'][0]['answer']
    print(f"fleak response: {json.dumps(answer)}")
    slack_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

    thread_ts = body.get("event").get("thread_ts") if "thread_ts" in body.get("event", {}) else body['event']['ts']

    slack_client.chat_postMessage(
        channel=body["event"]["channel"],
        text=answer,
        thread_ts=thread_ts
    )
    return answer
