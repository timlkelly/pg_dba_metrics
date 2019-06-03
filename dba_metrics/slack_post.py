#!/usr/bin/env python
# -*- coding: future_fstrings -*--
import os

import slackclient
from dotenv import find_dotenv, load_dotenv

override = False
if os.getenv("METRIC_ENV", "development") == "development":
    override = True

load_dotenv(find_dotenv(), override=override)

TOKEN = os.getenv("SLACK_TOKEN")
CHANNEL = os.getenv("CHANNEL")
HOSTNAME = os.getenv("HOSTNAME")

client = slackclient.SlackClient(TOKEN)


def slack_post(title="Test", message="Hello world!", color="#999999"):
    attach = dict(fallback=message, title=title, text=message, color=color)
    r = client.api_call(
        "chat.postMessage",
        channel=CHANNEL,
        attachments=[attach],
        username=f"{HOSTNAME} DBA alert"
    )
    return r


if __name__ == "__main__":
    slack_post(message="Something blah blah")