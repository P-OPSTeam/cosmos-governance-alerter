"""Governance vote allow the collection of cosmos governance vote"""
import json
import time
import traceback
from dateutil import parser
import requests
from utils import configure_logging

log = None

def read_config():
    """Read config file"""
    with open('config.json', 'r', encoding="utf-8") as config_file:
        config = json.load(config_file)
    return config

def is_vote_expired(vote):
    """Check whether a vote is expired"""
    current_time = int(time.time())
    return current_time >= parser.parse(vote['end_date']).timestamp()

def load_votes(app_config):
    """Load votes from app_config["votes_file"]"""
    log.info(f"loading votes on {app_config['votes_file']}")
    try:
        with open(app_config["votes_file"], 'r', encoding="utf-8") as votes_file:
            votes = json.load(votes_file)
    except FileNotFoundError:
        log.error("File not found, votes sets to {}")
        votes = {}
    return votes

def save_votes(app_config, votes):
    """Save votes"""
    log.info(f"Saving votes on {app_config['votes_file']}")
    with open(app_config["votes_file"], 'w', encoding="utf-8") as votes_file:
        json.dump(votes, votes_file, indent=2)

def remove_expired_votes(config, votes):
    """Remove expired vote"""
    log.info("Searching for expired votes")
    alerts_config = config['alerts_config']
    chain_config = config['chain_config']
    app_config = config['app_config']

    for chainname in votes:
        chain_votes = votes[chainname]
        for vote in chain_votes:
            if chainname not in chain_config:
                log.warning(f"{chainname} not configured")
            if is_vote_expired(vote) and chainname in chain_config:
                send_alert(vote, chain_config[chainname],
                           chainname, alerts_config, pdaction = "resolve")
        votes[chainname] = [vote for vote in votes[chainname] if not is_vote_expired(vote)]
    save_votes(app_config, votes)

def check_new_votes(chainname, chain_data, votes, alerts_config):
    """Checking for new governance vote"""
    try:
        next_page = True # use for looping over the rest answer page
        response = requests.get(f"{chain_data['api_endpoint']}", timeout=30)

        while next_page:
            if response.status_code == 200:
                response_data = response.json()
                if "code" in response_data or len(response_data) == 0:
                    log.error(f"http response is : {response_data}")
                    return

                vote_proposals = response_data.get("proposals", [])

                current_time = int(time.time())
                for vote in vote_proposals:
                    # v1beta1 and v1 has different api answer structure
                    log.debug(f"vote: {json.dumps(vote)}")
                    if "messages" in vote: #v1
                        vote_id = vote["id"]
                        message ="interchainstaking.v1.MsgGovReopenChannel"
                        if message in vote["messages"][0]["@type"]:
                        # testnet quicksilver id 14 onward
                            title = (vote["messages"][0]["title"]
                                     if 'title' in vote["messages"][0]
                                     else "No Title")
                        else:
                            title = (vote["messages"][0]["content"]["title"]
                                     if 'content' in vote["messages"][0] and
                                        'title' in vote["messages"][0]["content"]
                                     else "No Title")
                        if len(vote["messages"]) > 1: #v1 with multiple proposal
                            #ie quicksilver mainnet id 12
                            title = "Careful this has multiple proposal" + title
                    else: #v1beta1
                        vote_id = vote["proposal_id"]
                        title = (vote["content"]["title"]
                                 if 'title' in vote["content"]
                                 else "No Title")

                    end_date = parser.parse(vote["voting_end_time"]).timestamp()

                    if (
                        current_time < end_date and
                        (chainname not in votes or
                         not any(existing_vote["vote_id"] == vote_id
                                 for existing_vote in votes[chainname]))
                    ):
                        start_date = vote["submit_time"]
                        end_date = vote["voting_end_time"]
                        status = vote["status"]

                        new_vote = {
                            "vote_id": vote_id,
                            "title": title,
                            "start_date": start_date,
                            "end_date": end_date,
                            "status": status
                        }
                        if chainname not in votes:
                            votes[chainname]=[]

                        votes[chainname].append(new_vote)
                        send_alert(new_vote, chain_data, chainname, alerts_config)

                next_key = response_data['pagination']['next_key']
                next_page = next_key is not None
                if next_page: # call the next page
                    url = f"{chain_data['api_endpoint']}?pagination.key={next_key}"
                    response = requests.get(url, timeout=10)
            else:
                next_page = False
                log.error(response.json())

    except requests.exceptions.RequestException as e:
        log.error(f"Failed to fetch vote proposals from {chain_data['api_endpoint']}: {e}")
        log.error(traceback.format_exc())
        next_page = False
    except (KeyError, ValueError, TypeError) as e:
        log.error(f"Error processing vote proposals: {e}")
        log.error(traceback.format_exc())
        next_page = False

def send_pagerduty_alert(vote, chain_data, chainname, integration_key, action = "trigger"):
    """Send a pagerduty alert"""
    log.info(f"{action} PD alert for {chainname} vote id {vote['vote_id']}")
    endpoint = "https://events.pagerduty.com/v2/enqueue"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token token={integration_key}"
    }
    payload = {
        "event_action": action,
        "routing_key": integration_key,
        "dedup_key": f"{chain_data['network']}{chainname}{vote['vote_id']}",
        "payload": {
            "summary": (
                f"New Governance Vote: {chain_data['network']} "
                f"{chainname} #{vote['vote_id']}"
            ),
            "custom_details": f"{chain_data['explorer_governance']}/{vote['vote_id']}",
            "source": "Governance Vote Alerter",
            "severity": "info"
        }
    }

    response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
    if response.status_code == 202:
        log.info(f"PagerDuty alert {action} successfully")
    else:
        log.info(f"Failed to {action} PagerDuty alert")

def send_discord_alert(vote, chain_data, chainname, webhook_url):
    """Send a discord alert"""
    log.info(f"send Discord alert for {chainname} vote id {vote['vote_id']}")

    payload = {
        "content": (
            f"New **{chain_data['network']} {chainname}** "
            f"Governance Vote: **{vote['title']}**\n"
            f"{chain_data['explorer_governance']}/{vote['vote_id']}"
        )
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    if response.status_code == 204:
        log.info("Discord alert sent successfully")
    else:
        log.info("Failed to send Discord alert")

def send_alert(vote, chain_data, chainname, alerts_config, pdaction = "trigger"):
    """Send Alerts"""
    if alerts_config.get('pagerduty_enabled', False):
        integration_key = alerts_config.get('pagerduty_integration_key')
        send_pagerduty_alert(vote, chain_data, chainname, integration_key, pdaction)

    if alerts_config.get('discord_enabled', False) and pdaction == "trigger":
        webhook_url = alerts_config.get('discord_webhook_url')
        send_discord_alert(vote, chain_data, chainname, webhook_url)

def main():
    """main function"""
    config = read_config()
    alerts_config = config['alerts_config']
    chain_config = config['chain_config']
    app_config = config['app_config']
    timeout = app_config['timeout']

    global log
    log = configure_logging(app_config["logformat"], app_config["loglevel"])

    log.info("Governance Vote Alerter started")

    while True:
        votes = load_votes(app_config)
        remove_expired_votes(config, votes)

        for chain, chain_data in chain_config.items():
            log.info(f"Processing votes on {chain}")
            check_new_votes(chain, chain_data, votes, alerts_config)

        save_votes(app_config, votes)
        log.info(f"Waiting {timeout} minutes")
        time.sleep(timeout * 60)

if __name__ == '__main__':
    main()
