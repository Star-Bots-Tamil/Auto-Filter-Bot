import re
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from info import ADMINS, INDEX_EXTENSIONS
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType
from utils import temp, get_readable_time

lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    _, ident, chat, lst_msg_id, skip = query.data.split("#")
    if ident == 'accept':
        msg = query.message
        await msg.edit("<b>Starting Indexing...</b>")
        try:
            chat = int(chat)
        except ValueError:
            pass
        await index_files_to_db(int(lst_msg_id), chat, msg, bot, int(skip))
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.message.edit("Trying to cancel Indexing...")

@Client.on_message(filters.private & filters.incoming & filters.user(ADMINS))
async def send_for_index(bot, message):
    if lock.locked():
        return await message.reply('Wait until the previous process completes.')

    # Check for forwarded message or link
    if message.text and message.text.startswith("https://t.me"):
        try:
            msg_link = message.text.split("/")
            last_msg_id = int(msg_link[-1])
            chat_id = msg_link[-2]
            if chat_id.isnumeric():
                chat_id = int("-100" + chat_id)
        except:
            await message.reply('Invalid message link!')
            return
    elif message.forward_from_chat and message.forward_from_chat.type == ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        await message.reply('Please forward a valid message from a channel or send a valid message link.')
        return

    # Validate the chat
    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f'Error: {e}')

    if chat.type != ChatType.CHANNEL:
        return await message.reply("I can only index channels.")

    # Ask for skip count
    s = await message.reply("Send the number of messages to skip.")
    skip_msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await s.delete()
    try:
        skip = int(skip_msg.text)
    except:
        return await message.reply("Invalid number.")

    # Confirmation text with details
    confirmation_text = (
        f'Do you want to index the "{chat.title}" channel?\n'
        f'Total Messages: <code>{last_msg_id}</code>\n\n'
        'Reply with 1 (yes) or 0 (no).'
    )
    confirmation = await message.reply(confirmation_text)

    # Wait for user's response
    response = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await confirmation.delete()

    # Handle user response
    if response.text.strip() in ['1', 'yes', 'y', 'true']:
        await message.reply("Starting indexing process...")
        await index_files_to_db(int(last_msg_id), chat_id, message, bot, skip)
    elif response.text.strip() in ['0', 'no', 'n', 'false']:
        await message.reply("Indexing canceled by user.")
    else:
        await message.reply("Invalid response. Please reply with 1 (yes) or 0 (no).")

async def index_files_to_db(lst_msg_id, chat, msg, bot, skip):
    start_time = time.time()
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    badfiles = 0
    current = skip
    
    async with lock:
        try:
            async for message in bot.iter_messages(chat, lst_msg_id, skip):
                time_taken = get_readable_time(time.time()-start_time)
                if temp.CANCEL:
                    temp.CANCEL = False
                    await msg.edit(f"Successfully Cancelled!\nCompleted in {time_taken}\n\nSaved <code>{total_files}</code> files to Database!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nUnsupported Media: <code>{unsupported}</code>\nErrors Occurred: <code>{errors}</code>\nBad Files Ignoref: <code>{badfiles}</code>")
                    return
                current += 1
                if current % 30 == 0:
                    btn = [[
                        InlineKeyboardButton('CANCEL', callback_data=f'index#cancel#{chat}#{lst_msg_id}#{skip}')
                    ]]
                    try:
                        await msg.edit_text(text=f"Total messages received: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nUnsupported Media: <code>{unsupported}</code>\nErrors Occurred: <code>{errors}</code>\nBad Files Ignoref: <code>{badfiles}</code>", reply_markup=InlineKeyboardMarkup(btn))
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                elif not (str(media.file_name).lower()).endswith(tuple(INDEX_EXTENSIONS)):
                    unsupported += 1
                    continue
                media.caption = message.caption
                file_name = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.file_name))
                sts = await save_file(media)
                if sts == 'suc':
                    total_files += 1
                elif sts == 'dup':
                    duplicate += 1
                elif sts == 'err':
                    errors += 1
        except Exception as e:
            await msg.reply(f'Index canceled due to Error - {e}')
        else:
            await msg.edit(f'Succesfully saved <code>{total_files}</code> to Database!\nCompleted in {time_taken}\n\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nUnsupported Media: <code>{unsupported}</code>\nErrors Occurred: <code>{errors}</code>\nBad Files Ignoref: <code>{badfiles}</code>')
            
