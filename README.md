# fleak-slack-bot
A chatbot that allows users to ask questions based on channel chat history

`slack_chat_history.py` is the function that calls Slack API and fetch the chat history. It will parse the Slack response, replace mention tags with actual usernames.

`slack_proxy.py` contains the logic that accepts Slack bot events, forwards it to Fleak API and writes the final output back to Slack.


`slack_sdk_layer` is a python 3.11 compatible aws Lambda layer that contains Slack python SDK dependency. 