# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""
import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import PLAYLIST_IMG_URL, PRIVATE_BOT_MODE, adminlist
from AlexaMusic.misc import db
from strings import get_string
from AlexaMusic import YouTube, app
from AlexaMusic.misc import SUDOERS
from AlexaMusic.utils.database import (
    get_cmode,
    get_lang,
    get_playmode,
    get_assistant,
    get_playtype,
    is_active_chat,
    is_commanddelete_on,
    is_served_private_chat,
)
from AlexaMusic.utils.database.memorydatabase import is_maintenance
from AlexaMusic.utils.inline.playlist import botplaylist_markup

links = {}


def PlayWrapper(command):
    async def wrapper(client, message):
        # Check maintenance mode, skip if from channel (no from_user)
        if message.from_user and await is_maintenance() is False and message.from_user.id not in SUDOERS:
            return await message.reply_text(
                "Bot is under maintenance. Please wait for some time..."
            )
        if PRIVATE_BOT_MODE == str(True) and not await is_served_private_chat(
            message.chat.id
        ):
            await message.reply_text(
                "**Private Music Bot**\n\nOnly for authorized chats from the owner. Ask my owner to allow your chat first."
            )
            return await app.leave_chat(message.chat.id)
        if await is_commanddelete_on(message.chat.id):
            try:
                await message.delete()
            except Exception:
                pass
        language = await get_lang(message.chat.id)
        _ = get_string(language)
        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)
        if (
                        audio_telegram is None
            and video_telegram is None
            and url is None
            and len(message.command) < 2
        ):
            if "stream" in message.command:
                return await message.reply_text(_["str_1"])
            buttons = botplaylist_markup(_)
            return await message.reply_photo(
                photo=PLAYLIST_IMG_URL,
                caption=_["playlist_1"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        
        # Determine video and fplay flags BEFORE channel check
        if message.command[0][0] == "v":
            video = True
        else:
            if message.text and "-v" in message.text:
                video = True
            else:
                video = True if message.command[0][1] == "v" else None
        if message.command[0][-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_18"])
            fplay = True
        else:
            fplay = None
        
        # Check if message is from a channel (sender_chat exists and equals to the chat)
        if message.sender_chat:
            # If sender_chat.id == chat.id, it means it's sent from the channel itself
            if message.sender_chat.id == message.chat.id:
                # This is a channel message, show confirmation button
                import json
                command_data = {
                    "chat_id": message.chat.id,
                    "message_id": message.id,
                    "command_text": message.text or message.caption,
                    "command_list": message.command,  # Store parsed command list
                    "reply_to": message.reply_to_message.id if message.reply_to_message else None,
                    "video": video,  # Store video flag
                    "fplay": fplay,  # Store force play flag
                }
                callback_data = f"confirm_play_{message.chat.id}_{message.id}"
                
                # Store in memory (you can use database if needed)
                if not hasattr(app, 'pending_plays'):
                    app.pending_plays = {}
                app.pending_plays[callback_data] = command_data
                
                upl = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="✅ Confirm Play (Admin Only)",
                                callback_data=callback_data,
                            ),
                        ]
                    ]
                )
                return await message.reply_text(
                    "🎵 **Channel Play Request**\n\n"
                    "This command was sent from a channel. An admin needs to confirm this play request.\n"
                    "Click the button below to confirm and use your account as the requester.",
                    reply_markup=upl
                )
            else:
                # This is anonymous admin in a group
                upl = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="How to Fix this? ",
                                callback_data="AnonymousAdmin",
                            ),
                        ]
                    ]
                )
                return await message.reply_text(_["general_4"], reply_markup=upl)
        
        chat_id = message.chat.id
        channel = None
        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
          # Skip playtype check for channels or if from_user is None
        if message.from_user and playty != "Everyone" and message.from_user.id not in SUDOERS:
            admins = adminlist.get(message.chat.id)
            if not admins:
                return await message.reply_text(_["admin_18"])
            if message.from_user.id not in admins:
                return await message.reply_text(_["play_4"])
        
        # video and fplay already defined above before channel check

        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            try:
                try:
                    get = await app.get_chat_member(chat_id, userbot.id)
                except ChatAdminRequired:
                    return await message.reply_text(_["call_12"])
                if get.status in [
                    ChatMemberStatus.BANNED,
                    ChatMemberStatus.RESTRICTED,
                ]:
                    return await message.reply_text(
                        _["call_13"].format(
                            app.mention, userbot.id, userbot.name, userbot.username
                        )
                    )
            except UserNotParticipant:
                if chat_id in links:
                    invitelink = links[chat_id]
                else:
                    if message.chat.username:
                        invitelink = message.chat.username
                        try:
                            await userbot.resolve_peer(invitelink)
                        except Exception:
                            pass
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_12"])
                        except Exception as e:
                            return await message.reply_text(
                                _["call_14"].format(app.mention, type(e).__name__)
                            )

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                myu = await message.reply_text(_["call_15"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_14"].format(app.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    await myu.edit(_["call_16"].format(app.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(
                        _["call_14"].format(app.mention, type(e).__name__)
                    )

                links[chat_id] = invitelink

                try:
                    await userbot.resolve_peer(chat_id)
                except Exception:
                    pass

        return await command(
            client,
            message,
            _,
            chat_id,
            video,
            channel,
            playmode,
            url,
            fplay,
        )

    return wrapper
