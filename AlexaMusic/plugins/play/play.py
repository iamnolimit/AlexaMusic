"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import random
import string

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
from pyrogram.enums import ChatMemberStatus
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AlexaMusic import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, app
from AlexaMusic.core.call import Alexa
from AlexaMusic.utils import seconds_to_min, time_to_seconds
from AlexaMusic.utils.database import is_video_allowed
from AlexaMusic.utils.decorators.language import languageCB
from AlexaMusic.utils.decorators.play import PlayWrapper
from AlexaMusic.utils.formatters import formats
from AlexaMusic.utils.inline.play import (
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from AlexaMusic.utils.inline.playlist import botplaylist_markup
from AlexaMusic.utils.logger import play_logs
from AlexaMusic.utils.stream.stream import stream
from config import BANNED_USERS, lyrical
from strings import get_command
from AlexaMusic.utils.database import is_served_user

# Command
PLAY_COMMAND = get_command("PLAY_COMMAND")


async def play_commnd_core(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    """Core play function without decorator - can be called directly"""
    mystic = await message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    
    # Handle channel messages (from_user is None in channels)
    if message.from_user:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
    else:
        # For channel messages, use channel info
        user_id = message.chat.id
        user_name = message.chat.title or "Channel"
    
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
    if audio_telegram:
        if audio_telegram.file_size > config.TG_AUDIO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_5"])
        duration_min = seconds_to_min(audio_telegram.duration)
        if (audio_telegram.duration) > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, duration_min)
            )
        file_path = await Telegram.get_filepath(audio=audio_telegram)
        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(audio_telegram, audio=True)
            dur = await Telegram.get_duration(audio_telegram)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="telegram",
                    forceplay=fplay,                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
    elif video_telegram:
        if not await is_video_allowed(message.chat.id):
            return await mystic.edit_text(_["play_3"])
        if message.reply_to_message.document:
            try:
                ext = video_telegram.file_name.split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(
                        _["play_8"].format(f"{' | '.join(formats)}")
                    )
            except Exception:
                return await mystic.edit_text(
                    _["play_8"].format(f"{' | '.join(formats)}")
                )
        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_9"])
        file_path = await Telegram.get_filepath(video=video_telegram)
        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(video_telegram)
            dur = await Telegram.get_duration(video_telegram)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=True,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
    elif url:
        if await YouTube.exists(url):
            if "playlist" in url:
                try:
                    details = await YouTube.playlist(
                        url,
                        config.PLAYLIST_FETCH_LIMIT,
                        user_id,
                    )
                except Exception as e:
                    print(e)
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "yt"
                plist_id = (
                    (url.split("=")[1]).split("&")[0]
                    if "&" in url
                    else url.split("=")[1]
                )
                img = config.PLAYLIST_IMG_URL
                cap = _["play_10"]
            else:
                try:
                    details, track_id = await YouTube.track(url)
                except Exception as e:
                    print(e)
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_11"].format(
                    details["title"],
                    details["duration_min"],
                )
        elif await Spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID and not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text(
                    "ᴛʜɪs ʙᴏᴛ ᴄᴀɴ'ᴛ ᴩʟᴀʏ sᴩᴏᴛɪғʏ ᴛʀᴀᴄᴋs ᴀɴᴅ ᴩʟᴀʏʟɪsᴛs, ᴩʟᴇᴀsᴇ ᴄᴏɴᴛᴀᴄᴛ ᴍʏ ᴏᴡɴᴇʀ ᴀɴᴅ ᴀsᴋ ʜɪᴍ ᴛᴏ ᴀᴅᴅ sᴩᴏᴛɪғʏ ᴩʟᴀʏᴇʀ."
                )
            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_11"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_12"].format(user_name)
            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_12"].format(user_name)
            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_12"].format(user_name)
            else:
                return await mystic.edit_text(_["play_17"])
        elif await Apple.valid(url):
            if "album" in url:
                try:
                    details, track_id = await Apple.track(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_11"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Apple.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "apple"
                cap = _["play_13"].format(user_name)
                img = url
            else:
                return await mystic.edit_text(_["play_16"])
        elif await Resso.valid(url):
            try:
                details, track_id = await Resso.track(url)
            except Exception as e:
                return await mystic.edit_text(_["play_3"])
            streamtype = "youtube"
            img = details["thumb"]
            cap = _["play_11"].format(details["title"], details["duration_min"])
        elif await SoundCloud.valid(url):
            try:
                details, track_path = await SoundCloud.download(url)
            except Exception:
                return await mystic.edit_text(_["play_3"])
            duration_sec = details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="soundcloud",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        else:
            try:
                await Alexa.stream_call(url)
            except NoActiveGroupCall:
                await mystic.edit_text(
                    "ᴛʜᴇʀᴇ's ᴀɴ ᴇʀʀᴏʀ ɪɴ ᴛʜᴇ ʙᴏᴛ, ᴩʟᴇᴀsᴇ ʀᴇᴩᴏʀᴛ ɪᴛ ᴛᴏ sᴜᴩᴩᴏʀᴛ ᴄʜᴀᴛ ᴀs sᴏᴏɴ ᴀs ᴩᴏssɪʙʟᴇ."
                )
                return await app.send_message(
                    config.LOG_GROUP_ID,
                    "ᴩʟᴇᴀsᴇ ᴛᴜʀɴ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ ᴛᴏ sᴛʀᴇᴀᴍ ᴜʀʟ.",
                )
            except Exception as e:
                return await mystic.edit_text(_["general_3"].format(type(e).__name__))
            await mystic.edit_text(_["str_2"])
            try:
                await stream(
                    _,
                                    mystic,
                    user_id,
                    url,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=video,
                    streamtype="index",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await play_logs(message, streamtype="M3u8 or Index Link")
    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["playlist_1"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        slider = True
        # Handle case where message.text might be None
        if message.text:
            query = message.text.split(None, 1)[1]
        elif message.caption:
            query = message.caption.split(None, 1)[1]
        else:
            # Fallback: construct query from command list
            query = " ".join(message.command[1:])
        if "-v" in query:
            query = query.replace("-v", "")
        try:
            details, track_id = await YouTube.track(query)
        except Exception:
            return await mystic.edit_text(_["play_3"])
        streamtype = "youtube"
    if str(playmode) == "Direct":
        if not plist_type:
            if details["duration_min"]:
                duration_sec = time_to_seconds(details["duration_min"])
                if duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(
                            config.DURATION_LIMIT_MIN,
                            details["duration_min"],
                        )
                    )
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                return await mystic.edit_text(
                    _["play_15"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
            return await mystic.edit_text(err)
        await mystic.delete()
        return await play_logs(message, streamtype=streamtype)
    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                user_id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),            )
            return await play_logs(message, streamtype=f"Playlist : {plist_type}")
        else:
            if slider:
                buttons = slider_markup(
                    _,
                    track_id,
                    user_id,
                    query,
                    0,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_["play_11"].format(
                        details["title"].title(),
                        details["duration_min"],
                    ),                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype=f"Searched on Youtube")
            else:
                buttons = track_markup(
                    _,
                    track_id,
                    user_id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=img,
                    caption=cap,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype=f"URL Searched Inline")


@app.on_message(filters.command(PLAY_COMMAND) & (filters.group | filters.channel) & ~BANNED_USERS)
@PlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    """Main play command handler with decorator"""
    return await play_commnd_core(
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


@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_music(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except Exception:
            return
    chat_id = CallbackQuery.message.chat.id
    channel = None
    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except Exception:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    try:
        details, track_id = await YouTube.track(vidid, True)
    except Exception:
        return await mystic.edit_text(_["play_3"])
    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, details["duration_min"])
            )
    else:
        buttons = livestream_markup(
            _,
            track_id,
            CallbackQuery.from_user.id,
            mode,
            "c" if cplay == "c" else "g",
            "f" if fplay else "d",
        )
        return await mystic.edit_text(
            _["play_15"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    try:
        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("confirm_play_") & ~BANNED_USERS)
async def confirm_channel_play(client, CallbackQuery):
    """Handle channel play confirmation from admin"""
    try:
        # Check if user is admin in the channel
        chat_id = CallbackQuery.message.chat.id
        user_id = CallbackQuery.from_user.id
        
        try:
            member = await app.get_chat_member(chat_id, user_id)
            if member.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
                return await CallbackQuery.answer(
                    "⚠️ Only channel administrators can confirm play requests!",
                    show_alert=True
                )
        except Exception as e:
            print(f"Error checking admin status: {e}")
            return await CallbackQuery.answer(
                "⚠️ Unable to verify admin status!",
                show_alert=True
            )
        
        # Get stored command data
        callback_data = CallbackQuery.data.strip()
        if not hasattr(app, 'pending_plays') or callback_data not in app.pending_plays:
            return await CallbackQuery.answer(
                "⚠️ This play request has expired. Please send the command again.",
                show_alert=True
            )
        
        command_data = app.pending_plays[callback_data]
        del app.pending_plays[callback_data]
        
        # Get language
        from AlexaMusic.utils.database import get_lang
        from strings import get_string
        language = await get_lang(chat_id)
        _ = get_string(language)
        
        # Create a fake message object with admin's info
        import pyrogram
        from pyrogram.types import Message as OriginalMessage
        
        # Get original message
        try:
            original_msg = await app.get_messages(chat_id, command_data["message_id"])
        except Exception:
            return await CallbackQuery.answer(
                "⚠️ Original message not found!",
                show_alert=True
            )
        
        # Update the confirmation message
        await CallbackQuery.edit_message_text(
            f"✅ **Play Confirmed by Admin**\n\n"
            f"👤 Requester: {CallbackQuery.from_user.mention}\n"
            f"🎵 Processing your request..."
        )        # Now process the play command with admin's user info
        # We'll create a modified message context
        class ModifiedMessage:
            def __init__(self, original, admin_user, chat_id, stored_command, command_text):
                # Use CallbackQuery.message.chat if original.chat is None
                self.chat = original.chat if original.chat else CallbackQuery.message.chat
                self.id = original.id
                # Use stored command_text if original.text is None
                self.text = command_text if command_text else original.text
                self.caption = original.caption
                self.reply_to_message = original.reply_to_message
                self.from_user = admin_user  # Use admin's info instead of channel
                self.sender_chat = None  # Remove sender_chat to bypass channel check
                
                # Use stored command list from command_data
                self.command = stored_command if stored_command else []
                
                # Copy other attributes that might be needed
                if hasattr(original, 'entities'):
                    self.entities = original.entities
                else:
                    self.entities = None
                    
                if hasattr(original, 'caption_entities'):
                    self.caption_entities = original.caption_entities
                else:
                    self.caption_entities = None
                
            async def reply_text(self, *args, **kwargs):
                return await app.send_message(self.chat.id, *args, **kwargs)
            
            async def reply_photo(self, *args, **kwargs):
                return await app.send_photo(self.chat.id, *args, **kwargs)        # Create modified message with admin info and stored command
        modified_msg = ModifiedMessage(
            original_msg, 
            CallbackQuery.from_user, 
            chat_id,
            command_data.get("command_list", []),  # Pass stored command list
            command_data.get("command_text", "")   # Pass stored command text
        )
        
        # Debug: Print modified message attributes
        print(f"Debug - modified_msg.from_user: {modified_msg.from_user}")
        print(f"Debug - modified_msg.from_user.id: {modified_msg.from_user.id if modified_msg.from_user else 'None'}")
        print(f"Debug - modified_msg.chat: {modified_msg.chat}")
        print(f"Debug - modified_msg.chat.id: {modified_msg.chat.id if modified_msg.chat else 'None'}")
        print(f"Debug - modified_msg.command: {modified_msg.command}")
        
        # Process the command through the play wrapper
        from AlexaMusic.utils.decorators.play import PlayWrapper
        from AlexaMusic.utils.database import (
            get_playmode,
            get_playtype,
            is_commanddelete_on,
        )
        from AlexaMusic import YouTube
        
        # Get necessary data
        playmode = await get_playmode(chat_id)
        audio_telegram = (
            (original_msg.reply_to_message.audio or original_msg.reply_to_message.voice)
            if original_msg.reply_to_message
            else None
        )
        video_telegram = (
            (original_msg.reply_to_message.video or original_msg.reply_to_message.document)
            if original_msg.reply_to_message
            else None
        )
        url = await YouTube.url(original_msg)
          # Use stored video and fplay flags from command_data
        video = command_data.get("video", None)
        fplay = command_data.get("fplay", None)
          # Call the core play command directly (bypassing decorator)
        await play_commnd_core(
            client,
            modified_msg,
            _,
            chat_id,
            video,
            None,  # channel
            playmode,
            url,
            fplay,
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in confirm_channel_play: {e}")
        print(f"Full traceback:\n{error_trace}")
        try:
            await CallbackQuery.answer(
                f"⚠️ Error: {str(e)}",
                show_alert=True
            )
        except:
            pass


@app.on_callback_query(filters.regex("AnonymousAdmin") & ~BANNED_USERS)
async def anonymous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "ʏᴏᴜ'ʀᴇ ᴀɴ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ\n\nʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ ғᴏʀ ᴜsɪɴɢ ᴍᴇ.",
            show_alert=True,
        )
    except Exception:
        return


@app.on_callback_query(filters.regex("AlexaPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        videoid,
        user_id,
        ptype,
        mode,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except Exception:
            return
    chat_id = CallbackQuery.message.chat.id
    channel = None
    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except Exception:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except Exception:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except Exception:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except Exception:
            return await mystic.edit_text(_["play_3"])
    if ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except Exception:
            return await mystic.edit_text(_["play_3"])
    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        what,
        rtype,
        query,
        user_id,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except Exception:
            return
    what = str(what)
    rtype = int(rtype)
    if what == "F":
        query_type = 0 if rtype == 9 else int(rtype + 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except Exception:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_11"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )
    if what == "B":
        query_type = 9 if rtype == 0 else int(rtype - 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_11"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )
