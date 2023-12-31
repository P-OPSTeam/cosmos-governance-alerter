# Governance Vote Alerter

## Description
Cosmos Governance vote alerter

## Installation
```bash
cd ~
git clone https://github.com/P-OPSTeam/cosmos-governance-alerter.git
sudo apt update
sudo apt install python3 python3-virtualenv
cd cosmos-governance-alerter
virtualenv -p /usr/bin/python3 .venv
source .venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py | python3
pip install -r requirements.txt
```

## Configuration

```bash
cp config.json.example config.json
```

Use your favorite editor and edit config.json

- under app_config :
  - `timeout` represent how long we should wait before the next vote checks
  - `votes_file` is the filename that stores all the on-going vote in all supported network
  - `format`: The format of the log messages. Can be `json` or `text`.
  - `level`: The log level. Can be `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- under alerts_config
  - set to `true` the integration you would like to enable, and make sure to fill up the requirement information
- under chain_config and for each network :
  - `api_endpoint` is the governance api endpoint that list all the proposals
  - `network` is only used to provide more information in the alert
  - `explorer_governance` is the link without the proposal ID, ie program will add /<proposal ID>

## TODO 
- [ ] Add a license




