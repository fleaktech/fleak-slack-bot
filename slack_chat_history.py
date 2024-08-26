import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Initialize the Slack client with your bot token
client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])


class ChatHistory:
    def __init__(self):
        self.threads = []
        self.earliest = None
        self.latest = None

    def to_dict(self):
        return {
            "threads": [thread.to_dict() for thread in self.threads],
            "earliest": self.earliest,
            "latest": self.latest
        }


class Thread:
    def __init__(self):
        self.messages = []

    def to_dict(self):
        return {
            "messages": [message.to_dict() for message in self.messages]
        }


class Message:
    def __init__(self, user, timestamp, text):
        self.user = user
        self.timestamp = timestamp
        self.text = text

    def to_dict(self):
        return {
            "user": self.user,
            "timestamp": self.timestamp,
            "text": self.text
        }


def lambda_handler(event, context):
    print(f"received request: {json.dumps(event)}")
    earliest, latest = get_timestamps(event['hours_before'])
    channel_id = event["channel_id"]
    print(f"earliest={earliest}, latest={latest}")
    chat_history = fetch_chat_history(channel_id, earliest, latest)
    return chat_history.to_dict()


def get_timestamps(hours):
    # Get the current time
    current_time = datetime.now()

    # Calculate the time X hours before the current time
    time_before_x_hours = current_time - timedelta(hours=hours)

    # Convert both times to epoch timestamps
    current_epoch = int(current_time.timestamp())
    epoch_before_x_hours = int(time_before_x_hours.timestamp())

    return epoch_before_x_hours, current_epoch


def fetch_conversation_history(channel_id, earliest_ts, latest_ts):
    try:
        response = client.conversations_history(
            channel=channel_id,
            oldest=earliest_ts,
            latest=latest_ts,
            inclusive=True
        )
        return response['messages']
    except SlackApiError as e:
        print(f"Error fetching conversation history: {e.response['error']}")
        return []


def fetch_thread_messages(channel_id, thread_ts):
    try:
        response = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            inclusive=True
        )
        return response['messages'][1:]  # Exclude the first message (already fetched)
    except SlackApiError as e:
        print(f"Error fetching thread messages: {e.response['error']}")
        return []


def extract_user_ids(messages):
    user_ids = set()
    for msg in messages:
        if 'user' in msg:
            user_ids.add(msg['user'])
        # Find all mentioned users
        mentioned_users = re.findall(r"<@([A-Z0-9]+)>", msg['text'])
        user_ids.update(mentioned_users)
    return user_ids


def fetch_user_info(user_ids):
    users_info = {}
    try:
        # Fetch all members using users.list
        response = client.users_list()
        members = response['members']

        # First, save the real_name for users who are members
        for user in members:
            if user['id'] in user_ids:
                users_info[user['id']] = user['real_name']

        # For users not found in the members list, fetch individually
        missing_user_ids = user_ids - set(users_info.keys())

        for user_id in missing_user_ids:
            try:
                user_response = client.users_info(user=user_id)
                users_info[user_id] = user_response['user']['profile']['real_name']
            except SlackApiError as e:
                print(f"Error fetching info for user {user_id}: {e.response['error']}")

        return users_info

    except SlackApiError as e:
        print(f"Error fetching user info: {e.response['error']}")
        return users_info


def replace_mentions_with_names(text, user_info):
    for user_id, real_name in user_info.items():
        mention_tag = f"<@{user_id}>"
        text = text.replace(mention_tag, real_name)
    return text


def construct_chat_history(messages, user_info, channel_id):
    history = ChatHistory()

    threads = defaultdict(list)
    for msg in messages:
        if 'subtype' in msg and msg['subtype'] == "thread_broadcast":
            continue
        thread_ts = msg.get('thread_ts', msg['ts'])
        threads[thread_ts].append(msg)

    for thread_ts, msgs in threads.items():
        thread = Thread()
        # Include messages in the thread
        all_messages = msgs + fetch_thread_messages(channel_id, thread_ts)

        for msg in all_messages:

            if 'user' not in msg:
                continue

            # Replace mentions with real names
            text = replace_mentions_with_names(msg['text'], user_info)

            message = Message(
                user=user_info.get(msg['user'], "Unknown"),
                timestamp=datetime.utcfromtimestamp(float(msg['ts'])).isoformat(),
                text=text
            )
            thread.messages.append(message)
        history.threads.append(thread)

    if messages:
        history.earliest = datetime.utcfromtimestamp(float(messages[-1]['ts'])).isoformat()
        history.latest = datetime.utcfromtimestamp(float(messages[0]['ts'])).isoformat()

    return history


def fetch_chat_history(channel_id, earliest_ts, latest_ts):
    # Step 1: Fetch conversation history
    messages = fetch_conversation_history(channel_id, earliest_ts, latest_ts)

    # Step 2: Collect all user IDs
    user_ids = extract_user_ids(messages)

    # Step 3: Fetch user info
    user_info = fetch_user_info(user_ids)

    # Step 4: Construct the ChatHistory object
    chat_history = construct_chat_history(messages, user_info, channel_id)

    return chat_history
