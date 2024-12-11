import re
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageIdInvalid
from info import ADMINS, INDEX_EXTENSIONS
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType
from utils import temp, get_readable_time

lock = asyncio.Lock()

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

        # Attempt to edit the original message, with error handling
        try:
            await message.edit("Indexing process started...")
        except MessageIdInvalid:
            print("Message ID is invalid, skipping edit.")
        except Exception as e:
            print(f"Error editing message: {e}")

        await index_files_to_db(int(last_msg_id), chat_id, message, bot, skip)
    elif response.text.strip() in ['0', 'no', 'n', 'false']:
        await message.reply("Indexing canceled by user.")

        # Attempt to edit the original message, with error handling
        try:
            await message.edit("Indexing process canceled.")
        except MessageIdInvalid:
            print("Message ID is invalid, skipping edit.")
        except Exception as e:
            print(f"Error editing message: {e}")
    else:
        await message.reply("Invalid response. Please reply with 1 (yes) or 0 (no).")

        # Attempt to edit the original message, with error handling
        try:
            await message.edit("Invalid response. Please reply with 1 (yes) or 0 (no).")
        except MessageIdInvalid:
            print("Message ID is invalid, skipping edit.")
        except Exception as e:
            print(f"Error editing message: {e}")

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
            # Iterate over messages in the specified range
            async for message in bot.iter_messages(chat, lst_msg_id, skip):
                time_taken = get_readable_time(time.time() - start_time)
                
                # Check for cancellation flag
                if temp.CANCEL:
                    temp.CANCEL = False
                    await msg.edit(
                        f"Successfully Cancelled!\nCompleted in {time_taken}\n\n"
                        f"Saved <code>{total_files}</code> files to Database!\n"
                        f"Duplicate Files Skipped: <code>{duplicate}</code>\n"
                        f"Deleted Messages Skipped: <code>{deleted}</code>\n"
                        f"Non-Media messages skipped: <code>{no_media + unsupported}</code>\n"
                        f"Unsupported Media: <code>{unsupported}</code>\n"
                        f"Errors Occurred: <code>{errors}</code>\n"
                        f"Bad Files Ignored: <code>{badfiles}</code>"
                    )
                    return
                
                # Update progress every 30 messages
                current += 1
                if current % 30 == 0:
                    btn = [
                        [InlineKeyboardButton('CANCEL', callback_data=f'index#cancel#{chat}#{lst_msg_id}#{skip}')]
                    ]
                    try:
                        await msg.edit_text(
                            text=(
                                f"Total messages received: <code>{current}</code>\n"
                                f"Total messages saved: <code>{total_files}</code>\n"
                                f"Duplicate Files Skipped: <code>{duplicate}</code>\n"
                                f"Deleted Messages Skipped: <code>{deleted}</code>\n"
                                f"Non-Media messages skipped: <code>{no_media + unsupported}</code>\n"
                                f"Unsupported Media: <code>{unsupported}</code>\n"
                                f"Errors Occurred: <code>{errors}</code>\n"
                                f"Bad Files Ignored: <code>{badfiles}</code>"
                            ),
                            reply_markup=InlineKeyboardMarkup(btn)
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                
                # Process message content
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
                
                # Process the media file
                media.caption = message.caption
                file_name = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.file_name))
                sts = await save_file(media)

                # Track results of indexing process
                if sts == 'suc':
                    total_files += 1
                elif sts == 'dup':
                    duplicate += 1
                elif sts == 'err':
                    errors += 1
                elif sts == 'bad':
                    badfiles += 1

        except Exception as e:
            await msg.reply(f'Index canceled due to Error - {e}')
        else:
            # Final progress message
            time_taken = get_readable_time(time.time() - start_time)
            await msg.edit(
                f'Successfully saved <code>{total_files}</code> files to Database!\n'
                f'Completed in {time_taken}\n\n'
                f'Duplicate Files Skipped: <code>{duplicate}</code>\n'
                f'Deleted Messages Skipped: <code>{deleted}</code>\n'
                f'Non-Media messages skipped: <code>{no_media + unsupported}</code>\n'
                f'Unsupported Media: <code>{unsupported}</code>\n'
                f'Errors Occurred: <code>{errors}</code>\n'
                f'Bad Files Ignored: <code>{badfiles}</code>'
            )
            
