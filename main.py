import logging
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1

API_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "songs.json"
AUTHORIZED_USER_ID = 1918624551

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.reply("👋 Welcome to Squonk Radio V0.4.5!\nUse /setup to link your group.")

@dp.message_handler(commands=["setup"])
async def cmd_setup(message: types.Message):
    if message.chat.type != "private":
        return
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.reply("❌ You are not authorized to set up the bot.")
        return
    await message.reply("📮 Send me `GroupID: <your_group_id>` to register a group.")

@dp.message_handler(lambda message: message.chat.type == "private" and message.text.startswith("GroupID:"))
async def register_group(message: types.Message):
    group_id = message.text.split("GroupID:")[1].strip()
    if not group_id.lstrip("-").isdigit():
        await message.reply("❌ Invalid group ID format. Use `GroupID: 123456789`")
        return
    data = load_data()
    data[group_id] = []
    save_data(data)
    await message.reply(f"✅ Group ID `{group_id}` saved. Now send me .mp3 files!")

@dp.message_handler(content_types=types.ContentType.AUDIO)
async def handle_audio(message: types.Message):
    if message.chat.type != "private":
        return
    group_ids = load_data().keys()
    if not group_ids:
        await message.reply("❗ Please first send `GroupID: <your_group_id>` in this private chat.")
        return

    audio = message.audio
    file_info = await bot.get_file(audio.file_id)
    file_path = file_info.file_path
    file = await bot.download_file(file_path)
    file_name = f"{audio.file_unique_id}.mp3"

    with open(file_name, "wb") as f:
        f.write(file.read())

    audiofile = MP3(file_name, ID3=ID3)
    title = audiofile.get("TIT2", TIT2(encoding=3, text="Unknown")).text[0]
    artist = audiofile.get("TPE1", TPE1(encoding=3, text="Unknown")).text[0]

    data = load_data()
    for gid in data:
        data[gid].append({"file_id": audio.file_id, "title": title, "artist": artist})
    save_data(data)

    await message.reply(f"✅ Saved `{title}` by `{artist}`.")

@dp.message_handler(commands=["play"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_play(message: types.Message):
    group_id = str(message.chat.id)
    data = load_data()
    songs = data.get(group_id)
    if not songs:
        await message.reply("❌ No songs found for this group.")
        return

    song = songs[0]
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⏭️ Next", callback_data="next"),
        InlineKeyboardButton("📀 Playlist", callback_data="playlist")
    )
    await message.answer_audio(song["file_id"], caption="🎵 Squonking time!", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "next")
async def callback_next(call: types.CallbackQuery):
    group_id = str(call.message.chat.id)
    data = load_data()
    songs = data.get(group_id, [])
    if not songs:
        await call.message.edit_caption("❌ Playlist is empty.")
        return
    songs.append(songs.pop(0))
    save_data(data)
    song = songs[0]
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⏭️ Next", callback_data="next"),
        InlineKeyboardButton("📀 Playlist", callback_data="playlist")
    )
    await call.message.edit_media(
        types.InputMediaAudio(media=song["file_id"], caption="🎵 Squonking time!"),
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "playlist")
async def callback_playlist(call: types.CallbackQuery):
    group_id = str(call.message.chat.id)
    data = load_data()
    songs = data.get(group_id, [])
    if not songs:
        await call.message.answer("❌ Playlist is empty.")
        return

    text = "🎵 Playlist:\n"
    for i, song in enumerate(songs, 1):
        text += f"{i}. {song['title']} by {song['artist']}\n"
    await call.message.answer(text)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
