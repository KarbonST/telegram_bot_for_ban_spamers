from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

start_router = Router()

@start_router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет, я бот модератор!"
    )

@start_router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Я помогаю удалять спам в чатах каналов"
    )

