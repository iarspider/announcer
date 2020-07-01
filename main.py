#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import asyncio
import datetime
import sys
from pathlib import Path

import discord
import requests
import simplejson

from config import *
from enums import VkUserPermissions

scopes = str(VkUserPermissions.PHOTOS + VkUserPermissions.VIDEO + VkUserPermissions.WALL + VkUserPermissions.OFFLINE)
auth_url = 'https://oauth.vk.com/authorize'
callback_uri = 'https://localhost'
api_version = '5.103'
vk_access_token = ""


class VKException(Exception):
    pass


def vk_get(method, **kwargs):
    kwargs['access_token'] = vk_access_token
    kwargs['v'] = api_version
    r = requests.get("https://api.vk.com/method/{0}".format(method), kwargs)
    r.raise_for_status()
    # print("GET", r.url)
    res = r.json()
    if res.get("error"):
        raise VKException(res['error']['error_msg'])
    return res['response']


def vk_upload_photo(url, filenames):
    files = {}
    for i, file in enumerate(filenames[:5]):
        files["file" + str(i)] = open(file, "rb")
    # kwargs['access_token'] = access_token
    r = requests.post(url, files=files)
    # print("POST", r.url)
    res = r.json()
    if res.get("error"):
        raise VKException(res['error']['error_msg'])
    return res


def post(text, photo_id=None, video_id=None, date=-1):
    text = text.replace('<', '').replace('>', '')
    attachments = []
    if photo_id is not None:
        attachments.append(photo_id)

    if video_id is not None:
        attachments.append(video_id)

    if int(datetime.datetime.now().timestamp()) < int(date):
        res = vk_get("wall.post", owner_id=-vk_group_id, from_group=1, message=text, attachments=','.join(attachments),
                     publish_date=date)
    # res = vk_get("wall.post", owner_id=-grouq_id, from_group=1, message=text, attachments=photo_id, publish_date=date)
    else:
        res = vk_get("wall.post", owner_id=-vk_group_id, from_group=1, message=text, attachments=','.join(attachments))
        post_id = res['post_id']
        print(f"Post url: https://vk.com/wall-{vk_group_id}_{post_id}")
        # print("Reposting...")
        # vk_get("wall.repost", object=f"wall-{vk_group_id}_{post_id}", group_id=vk_group_id)
        # print("Reposted")


def post_photo(image):
    res = vk_get("photos.getWallUploadServer", group_id=vk_group_id)
    # pprint.pprint(res)
    # sys.stdout.flush()
    res = vk_upload_photo(res['upload_url'], [image])
    # pprint.pprint(res)
    # sys.stdout.flush()
    res = vk_get("photos.saveWallPhoto", group_id=vk_group_id, photo=res['photo'], server=res['server'],
                 hash=res['hash'])
    # pprint.pprint(res)
    # sys.stdout.flush()
    photo_id = "photo{owner_id}_{id}".format(**(res[0]))
    return photo_id


def authorize():
    global vk_access_token
    try:
        with open("secret.json", "r") as f:
            vk_access_token = simplejson.load(f)["key"]
    except (KeyError, IOError, FileNotFoundError) as e:
        pass

    if not vk_access_token:
        print("Please open the following URL to start...")
        print("{0}?client_id={1}&display=mobile&redirect_uri=&scope={3}&response_type=token&v={4}&state=12345".format(
            auth_url,
            vk_client_id,
            "https://oauth.vk.com/blank.html",
            scopes,
            api_version)
        )

        redirect_uri = input("Please input callback URL")
        redirect_uri = redirect_uri.split('#', 1)[1]
        if redirect_uri.startswith('error'):
            print("Oops!")
            return

        code = redirect_uri.split('=', 1)[1].split('&', 1)[0]
        with open("secret.json", "w") as f:
            simplejson.dump({'key': code}, f)

        vk_access_token = code


def post_vk(args, photo):
    authorize()

    print(f"Uploading photo from {str(photo)}...")
    photo_id = post_photo(str(photo))
    print(f"Done, id: {photo_id}")

    print("Creating a post...")
    post(args.message, photo_id)


def post_discord(args, photo):
    print("Creating an announcement in Discord...")
    discord_bot = discord.Client()

    @discord_bot.event
    async def on_ready():
        guild: discord.guild = discord.utils.find(lambda g: g.name == discord_guild_name, discord_bot.guilds)

        if guild is None:
            raise RuntimeError(f"Failed to join Discord server {discord_guild_name}!")

        discord_channel: discord.channel.TextChannel = discord.utils.find(lambda c: c.name == discord_channel_name,
                                                                          guild.channels)
        if discord_channel is None:
            raise RuntimeError(f"Failed to join Discord channel {discord_channel_name}!")

        role: discord.role = discord.utils.find(lambda r: r.name == discord_role_name, guild.roles)
        if role is None:
            raise RuntimeError(f"No role {discord_role_name} in server {discord_guild_name}!")

        print(f"Ready | {discord_bot.user} @ {guild.name}")

        await discord_channel.send(content=f'<@&{role.id}> {args.message}', file=discord.File(str(photo)))
        print("Done")
        print("Shutting down")
        asyncio.ensure_future(discord_bot.close())

        # print(f"Ready | {discord_bot.user} @ {guild.name}")

    discord_bot.run(discord_bot_token)


def main(*argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--message")
    parser.add_argument("-p", "--photo")
    if argv:
        sys.argv = sys.argv[0:1]
        sys.argv.extend(argv)

    args = parser.parse_args()

    if not Path(args.photo).is_absolute():
        photo = Path(photo_root) / args.photo
    else:
        photo = Path(args.photo)

    post_vk(args, photo)
    post_discord(args, photo)

    print("All done")


if __name__ == '__main__':
    main()