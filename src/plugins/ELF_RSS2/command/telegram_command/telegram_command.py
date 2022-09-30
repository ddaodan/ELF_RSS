import asyncio
from typing import Any, List, Optional

from telethon import Button, TelegramClient, events
from telethon.tl.patched import Message


class InputButton:
    def __init__(self, text: str, data: str):
        self.text = text
        self.data = data


async def wait_msg_callback(
    bot: TelegramClient,
    event: events.CallbackQuery.Event,
    msg: str,
    timeout: float = 60,
    placeholder: Optional[str] = None,
) -> Message:
    # 等待用户发送消息
    # 需要用户输入的信息
    async with bot.conversation(
        await event.get_chat(), timeout=timeout, exclusive=False
    ) as conv:
        # @用户
        if event.sender.username:
            msg += f" @{event.sender.username}"
        await conv.send_message(
            msg,
            buttons=Button.force_reply(
                single_use=True,
                selective=True,
                placeholder=placeholder,
            ),
            # 这里之所以要 -1 是因为 需要用户发送命令那条消息的id
            reply_to=event.message_id - 1,  # FIXME: 遇到多人同时聊天可能不符合预期
        )
        while True:
            e = await conv.get_response()
            if e.sender_id == event.sender_id:
                return e.message


async def wait_btn_callback(
    bot: TelegramClient,
    event: events.CallbackQuery.Event,
    tips_text: str,
    btns: List[InputButton],
    remove_btn: bool = True,
    timeout: float = 10,
):
    datas = [btn.data for btn in btns]
    # 一行三个按钮，从 self.btns 里取
    buttons = [
        map(lambda b: Button.inline(b.text, b.data), btns[i : i + 3])
        for i in range(0, len(btns), 3)
    ]
    # 等待用户点击按钮
    async with bot.conversation(
        await event.get_chat(), timeout=timeout, exclusive=False
    ) as conv:
        ans = await conv.send_message(tips_text, buttons=buttons)
        try:
            while True:
                # 等待用户点击按钮
                res = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == event.sender_id),
                    timeout=timeout,
                )
                # bytes 转字符串
                data: str = res.data.decode()
                if data in datas:
                    return data
        finally:
            if remove_btn:
                # 删除按钮
                await ans.delete()


class CommandInputBase:
    def __init__(
        self,
        bot: TelegramClient,
        event: events.CallbackQuery.Event,
        tips_text: str,
    ):
        self.bot = bot
        self.event = event
        self.tips_text = tips_text

    async def input(self) -> None:
        pass


class CommandInfo:
    def __init__(self, name: str, command: str, description: str):
        self.name = name
        self.command = command
        self.description = description


class CommandField:
    def __init__(
        self,
        description: str,
        key: str,
        field_type: CommandInputBase,
        value: Any = None,
    ):
        self.description = description
        self.key = key
        self.field_type = field_type
        self.value = value


class CommandInputText(CommandInputBase):
    def __init__(
        self,
        bot: TelegramClient,
        event: events.CallbackQuery.Event,
        tips_text: str,
    ):
        super().__init__(bot, event, tips_text)

    async def input(
        self, placeholder: Optional[str] = None, timeout: float = 60
    ) -> Optional[Message]:
        try:
            return await wait_msg_callback(
                self.bot,
                self.event,
                self.tips_text,
                timeout=timeout,
                placeholder=placeholder,
            )

        except asyncio.TimeoutError:
            await self.event.answer("超时，已取消")
            return None


class CommandInputBtns(CommandInputBase):
    def __init__(
        self,
        bot: TelegramClient,
        event: events.CallbackQuery.Event,
        tips_text: str,
        btns: List[InputButton],
    ):
        super().__init__(bot, event, tips_text)
        self.btns = btns

    async def input(self, timeout: float = 60, remove_btn: bool = True):

        try:
            return await wait_btn_callback(
                self.bot,
                self.event,
                tips_text=self.tips_text,
                btns=self.btns,
                remove_btn=remove_btn,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await self.event.answer("超时，已取消")
            return None


class CommandInputBtnsBool(CommandInputBtns):
    def __init__(
        self,
        bot: TelegramClient,
        event: events.CallbackQuery.Event,
        tips_text: str,
    ):
        super().__init__(
            bot,
            event,
            tips_text,
            [InputButton("True", "True"), InputButton("False", "False")],
        )

    async def input(self, timeout: float = 60, remove_btn: bool = True):
        return await super().input(timeout=timeout, remove_btn=remove_btn) == "True"


class CommandInputBtnsCancel(CommandInputBtns):
    def __init__(
        self,
        bot: TelegramClient,
        event: events.CallbackQuery.Event,
        tips_text: str,
    ):
        super().__init__(
            bot,
            event,
            tips_text,
            [InputButton("取消", "cancel")],
        )

    async def input(self, timeout: float = 60, remove_btn: bool = True):
        return await super().input(timeout=timeout, remove_btn=remove_btn) == "cancel"