import logging
import logging.config

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.WARNING)

import asyncio
from telethon import TelegramClient
from pyrogram import Client
from info import SESSION, USER_STRING_SESSION, API_ID, API_HASH, BOT_TOKEN, ADMINS

async def main():
    """Main function to start the user bot and bot."""

    # Initialize Telethon clients
    user_bot = TelegramClient(StringSession(USER_STRING_SESSION), API_ID, API_HASH)
    bot = Client(name='Auto-Filter-Bot', API_ID, API_HASH, bot_token=BOT_TOKEN)
    
    # Start both bots
    await user_bot.start()
    await bot.start()

    # Send a message to admin after bot starts
    try:
        await bot.send_message(ADMINS, "✅ Bot and User has Successfully Started!")
        print("Message sent to admin.")
    except Exception as e:
        print(f"Error sending message to admin: {e}")

    # Example: just stopping the bots after they are started
    await user_bot.disconnect()
    await bot.disconnect()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
