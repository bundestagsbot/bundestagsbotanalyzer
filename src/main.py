import asyncio
from threading import Thread
from datetime import datetime, timedelta
import os.path
import json

import discord
from discord.errors import LoginFailure
from discord.utils import get as discord_fetch

from utils import Console, cfg, app_scheduler, SuccessEmbed, ErrorEmbed, InfoEmbed

loop = asyncio.new_event_loop()
app_scheduler.main_loop = loop
client = discord.Client(loop=loop)
SHL = Console(prefix="BundestagsBot")

CONTENT_PATH = "content" if os.path.isdir("content") else "content-default"
SHL.info(f"Using content path: {CONTENT_PATH}")

about_embed = InfoEmbed(title="Help")
with open(os.path.join("static", "info.txt"), "r", encoding="utf-8") as fh:
    about_embed.description = fh.read()


class UserStat:
    def __init__(self, user_obj: discord.Member):
        self.user_obj = user_obj
        self.count = 1

    def __str__(self):
        return f"{self.user_obj.display_name}: {self.count}"


async def assign_active_member(*args):
    SHL.info("Fetching last messages.")
    guild = await client.fetch_guild(cfg.get("guild_id"))
    SHL.debug(f"Guild: {guild}")

    # Remove all "active" members
    SHL.info("Remove active role from all users.")
    for role in cfg.get("apply_roles"):
        role = guild.get_role(role)
        async for member in guild.fetch_members():
            if role not in member.roles:
                continue
            SHL.debug(f"Remove {role} from {member}")
            try:
                await member.remove_roles(role)
            except:
                SHL.debug(f"Failed for {member}")

    # Find new active members
    channels = await guild.fetch_channels()

    announcement_channel = await client.fetch_channel(cfg.get("announce_channel"))
    log_channel = await client.fetch_channel(cfg.get("log_channel"))

    users = {}
    before = datetime.now()
    after = datetime.now() - timedelta(days=31)

    with open(os.path.join(CONTENT_PATH, "unsubs.json"), "r") as fh:
        unsubs = json.load(fh)["unsub_ids"]

    SHL.debug(f"{len(unsubs)} users unsubbed.")

    for channel in channels:
        if not isinstance(channel, discord.TextChannel):
            continue
        if channel.id in cfg.get("exclude_channels"):
            continue

        SHL.debug(f"Fetching {channel.name}")
        async for message in channel.history(limit=None, before=before, after=after):
            uid = message.author.id
            if uid in unsubs:  # filter opt-out user
                continue
            if uid in users:
                users[uid].count += 1
            else:
                users[uid] = UserStat(message.author)

    sorted_list = sorted([x for x in users.values() if x.count >= cfg.get("needed_messages")],
                         key=lambda item: item.count, reverse=True)
    SHL.debug(f"{len(sorted_list)} users sent enough messages.")

    log_embed = InfoEmbed(title="Aktivsten User")
    for stat in sorted_list:  # active user
        try:
            member = await guild.fetch_member(stat.user_obj.id)
        except:  # if user left or got banned
            continue
        SHL.debug(f"Apply roles for {member}")
        log_embed.description += f"{member.mention} : {stat.count} Nachrichten.\n"
        for role in cfg.get("apply_roles"):
            assign_role = discord_fetch(guild.roles, id=role)
            try:
                await member.add_roles(assign_role)
            except:
                SHL.debug(f"Failed for {stat.user_obj}")
                break
    await log_channel.send(embed=log_embed)

    announcement = InfoEmbed(title="Aktivsten User", description="Für die Auswahl der Stammmitglieder.\n")
    for stat in sorted_list[:3]:  # most active user
        member = await guild.fetch_member(stat.user_obj.id)
        announcement.description += f"{member.mention} : {stat.count} Nachrichten.\n"

    await announcement_channel.send(embed=announcement)
    await log_channel.send(embed=announcement)
    SHL.info("Done.")


@client.event
async def on_message(message: discord.Message):
    if message.content.startswith("_analyze"):
        SHL.info(f"{message.author} used {message.content}")
        if any([x in message.content.lower() for x in ["help", "info", "details", "about"]]):
            await message.channel.send(embed=about_embed)
            return

        if "true" in message.content.lower():
            with open(os.path.join(CONTENT_PATH, "unsubs.json"), "r") as fh:
                data = json.load(fh)
            try:
                data["unsub_ids"].remove(message.author.id)
            except ValueError:
                pass
            with open(os.path.join(CONTENT_PATH, "unsubs.json"), "w") as fh:
                json.dump(data, fh)
            await message.channel.send(embed=SuccessEmbed(title="Analyzer",
                                                          description="Deine Nachrichten werden nun wieder erfasst."))
            return

        if "false" in message.content.lower():
            with open(os.path.join(CONTENT_PATH, "unsubs.json"), "r") as fh:
                data = json.load(fh)
            if message.author.id not in data["unsub_ids"]:
                data["unsub_ids"].append(message.author.id)
            with open(os.path.join(CONTENT_PATH, "unsubs.json"), "w") as fh:
                json.dump(data, fh)
            await message.channel.send(embed=SuccessEmbed(title="Analyzer",
                                                          description="Deine Nachrichten werden nun nicht erfasst.\n"
                                                                      "Um diesen Vorgang rückgängig zu machen verwende `_analyze true`."))
            return


def start_bot():
    try:
        token = cfg.options["BOT_TOKEN"]
    except KeyError:
        SHL.error(f"========================")
        SHL.error(f"'BOT_TOKEN' not found in config files!")
        return
    try:
        SHL.info(f"Logging in.")
        client.run(token, reconnect=cfg.options.get("use_reconnect", False))
    except LoginFailure:
        SHL.error(f"========================")
        SHL.error(f"Login failure!")
        SHL.error(f"Please check your token.")
        return


thread_sched = Thread(target=app_scheduler.schedule_check, name="sched")
thread_sched.start()
app_scheduler.schedule_daily(func=assign_active_member, tag="test")
start_bot()
