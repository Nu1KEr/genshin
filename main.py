import argparse
import asyncio
import logging
import os
import pathlib
import io
import json
import pytz
from dotenv import load_dotenv
from datetime import datetime
import requests
import genshin
import jinja2
from bs4 import BeautifulSoup
import time

logger = logging.getLogger()
load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument("-t", "--template", default="template.html", type=pathlib.Path)
parser.add_argument("-o", "--output", default="stats.html", type=pathlib.Path)
parser.add_argument("-c", "--cookies", default=None)
parser.add_argument("-l", "--lang", "--language", choices=genshin.LANGS, default="ru-ru")


def format_date(date: "datetime"):
    tz = pytz.timezone("Europe/Moscow")
    now = date.now(tz=tz)
    fmt = f"{now.strftime('%b')} \
            {now.strftime('%d')}, \
            {now.strftime('%Y')} \
            {now.strftime('%H:%M %z')}"
    return fmt


async def main():
    args = parser.parse_args()

    # type: <class 'str'>
    _c = os.getenv("COOKIES")
    # must loads to dict
    cookies = json.loads(_c)

    client = genshin.Client(cookies, debug=False, game=genshin.Game.GENSHIN)
    await genshin.utility.update_characters_any()
    user = await client.get_full_genshin_user(0, lang='ru-ru')
    abyss = user.abyss.current if user.abyss.current.floors else user.abyss.previous
    diary = await client.get_genshin_diary()

    try:
        await client.claim_daily_reward(lang=args.lang, reward=False)
    except genshin.AlreadyClaimed:
        pass
    finally:
        reward = await client.claimed_rewards(lang=args.lang).next()
        reward_info = await client.get_reward_info()

    template: jinja2.Template = jinja2.Template(args.template.read_text())
    rendered = template.render(
        user=user,
        lang=args.lang,
        abyss=abyss,
        reward=reward,
        diary=diary,
        reward_info=reward_info,
        updated_at=format_date(reward.time),
        _int=int
    )
    args.output.write_text(rendered)
    url = "https://scoofszlo.github.io/genshinimpact_codetracker/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    codes_file = pathlib.Path(__file__).parent.resolve() / "codes.txt"
    active_codes = []
    for code in soup.find_all('p', class_='reward_code'):
        active_codes.append(code.text)

    used_codes = codes_file.open().read().split("\n")
    new_codes = list(filter(lambda x: x not in used_codes and x != "", active_codes))
    failed_codes = []
    for code in new_codes[:-1]:
        try:
            await client.redeem_code(code)
        except Exception as e:
            failed_codes.append(code)
        time.sleep(5.2)
    if len(new_codes) != 0:
        try:
            await client.redeem_code(new_codes[-1])
        except Exception as e:
            failed_codes.append(new_codes[-1])

    redeemed_codes = list(filter(lambda x: x not in failed_codes, new_codes))
    if len(redeemed_codes) != 0:
        print("Redeemed " + str(len(redeemed_codes)) + " new codes: " + ", ".join(redeemed_codes))
    else:
        print("No new codes found")

    # %% Add new codes to used codes

    used_codes.extend(new_codes)
    io.open(codes_file, "w", newline="\n").write("\n".join(used_codes))



if __name__ == "__main__":
    asyncio.run(main())
