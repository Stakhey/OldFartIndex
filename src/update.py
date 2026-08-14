from pathlib import Path
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "raw" / "primary" / "world_leaders.csv"

COUNTRY = "FRA"


df = pd.read_csv(DATA)

country_row = df[df["iso3"] == COUNTRY].iloc[0]

wiki_monitor = country_row["wiki_monitor"]
leader_name = country_row["leader_name"]

print(f"Country: {COUNTRY}")
print(f"Saved leader: {leader_name}")
print(f"Wikipedia page: {wiki_monitor}") 


response = requests.get(
    wiki_monitor,
    headers={"User-Agent": "OldFartIndex/1.0"}
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for element in soup.find_all(attrs={"data-mw": True}):
    try:
        data = json.loads(element["data-mw"])
    except json.JSONDecodeError:
        continue

    for part in data.get("parts", []):
        template = part.get("template")

        if not template:
            continue

        params = template.get("params", {})

        if "incumbent" not in params:
            continue

        incumbent = params["incumbent"]["wt"].strip()

        if incumbent.startswith("[[") and incumbent.endswith("]]"):
            link_target = incumbent[2:-2]

            if "|" in link_target:
                link_target = link_target.split("|")[0]

            leader_name = link_target.replace("_", " ")

            leader_wiki = (
                "https://en.wikipedia.org/wiki/"
                + link_target.replace(" ", "_")
            )

            print("Leader:", leader_name)
            print("Wikipedia:", leader_wiki)