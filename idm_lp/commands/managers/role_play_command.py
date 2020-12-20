from typing import Optional

import requests
from pydantic import ValidationError
from vkbottle.rule import FromMe
from vkbottle.user import Blueprint, Message
from gettext import gettext as _

from idm_lp.models import RolePlayCommand
from idm_lp.utils import edit_message
from idm_lp.utils.temp import RolePlayCommandPydantic, RolePlayCommandTemp

user = Blueprint(
    name='role_play_commands_blueprint'
)

all_role_play_cmd = [
    "<p:prefix_service> <role_play_command:role_play_command> всех",
    "<p:prefix_service> <role_play_command:role_play_command> всем",
]
user_id_cmd = "<p:prefix_service> <role_play_command:role_play_command> [id<user_id:int>|<name>]"
no_user_id_cmd = "<p:prefix_service> <role_play_command:role_play_command>"


async def get_role_play_message(
        message: Message,
        role_play_command: RolePlayCommandPydantic,
        user_id: Optional[int] = None,
        call_all: bool = False
) -> str:
    called_user = (await message.api.users.get(fields=["sex"]))[0]

    pattern = role_play_command.formatter_woman if called_user.sex == 1 else role_play_command.formatter_man

    first_user = f"[id{called_user.id}|{called_user.first_name} {called_user.last_name}]"
    if call_all:
        return pattern.format(
            first_user=first_user,
            second_user=role_play_command.all_ending
        )

    second_user = (await message.api.users.get(user_ids=user_id, name_case=role_play_command.gen.value))[0]
    last_user = f"[id{second_user.id}|{second_user.first_name} {second_user.last_name}]"
    return pattern.format(
        first_user=first_user,
        second_user=last_user
    )


@user.on.message_handler(FromMe(), text=all_role_play_cmd)
async def role_play_command_wrapper(
        message: Message,
        role_play_command: RolePlayCommandPydantic,
        **kwargs
):
    await edit_message(
        message,
        await get_role_play_message(
            message,
            role_play_command,
            call_all=True
        )
    )


@user.on.message_handler(FromMe(), text=user_id_cmd)
async def role_play_command_wrapper(
        message: Message,
        role_play_command: RolePlayCommandPydantic,
        user_id: int,
        **kwargs
):
    await edit_message(
        message,
        await get_role_play_message(
            message,
            role_play_command,
            user_id=user_id
        )
    )


@user.on.message_handler(FromMe(), text=no_user_id_cmd)
async def role_play_command_wrapper(
        message: Message,
        role_play_command: RolePlayCommandPydantic,
        **kwargs
):
    user_id = None
    if message.reply_message:
        user_id = message.reply_message.from_id
    if message.fwd_messages:
        user_id = message.fwd_messages[0].from_id

    if not user_id:
        return

    if user_id < 0:
        return

    await edit_message(
        message,
        await get_role_play_message(
            message,
            role_play_command,
            user_id=user_id
        )
    )


@user.on.message_handler(FromMe(), text="<p:prefix_service> рп")
async def show_rp_commands(message: Message, **kwargs):
    text = _("📃 Доступные РП-команды:\n")
    index = 1
    for rp_cmd in RolePlayCommandTemp.data:
        text += f"{index}. {rp_cmd.name}\n"
        index += 1
    text += _("\nВсего РП-комманд: %d\nРП-комманд в памяти: %d") % (
        await RolePlayCommand.all().count(),
        len(RolePlayCommandTemp.data)
    )
    await edit_message(
        message,
        text
    )


@user.on.message_handler(FromMe(), text="<p:prefix_service> рп обновить")
async def show_rp_commands(message: Message, **kwargs):
    await RolePlayCommandTemp.load_from_db()
    await edit_message(
        message,
        _("✅ РП-комманды обновлены")
    )


def check(sub_strings: list, strings: list) -> bool:
    for sub in sub_strings:
        for string in strings:
            if sub not in string:
                return False
    return True


@user.on.message_handler(FromMe(), text="<p:prefix_service> рп загрузить <download_url:url>")
async def wrapper(message: Message, download_url: str, **kwargs):
    try:
        data = requests.get(download_url).json()
    except Exception as ex:
        await edit_message(
            message,
            _("Произошла ошибка при загрузке страницы: %s") % str(ex)
        )
        return
    text = _("Импорт РП-команд со страницы %s\n") % download_url
    index = 0
    for rp in data['role_play_commands']:
        index += 1
        try:
            RolePlayCommandPydantic(**rp)
        except ValidationError as ex:
            text += _("%d. Произошла ошибка валидации: %s\n") % (index, str(ex))
            continue
        if not check(['{first_user}', '{second_user}'], [rp['formatter_man'], rp['formatter_woman']]):
            text += _("%d. Произошла ошибка валидации: отсутствует форматтер\n") % index
            continue
        try:
            rp = await RolePlayCommandTemp.create(**rp)
            text += _("%d. РП-команда «%s» импортирована\n") % (index, rp.name)
        except:
            text += _("%d. Ошибка импорта\n") % index
    await edit_message(
        message,
        text
    )


@user.on.message_handler(FromMe(), text="<p:prefix_service> -рп <name>")
async def wrapper(message: Message, name: str, **kwargs):
    if await RolePlayCommandTemp.delete(name):
        await edit_message(
            message,
            _("✅ РП-команда «%s» удалена") % name
        )
        return
    else:
        await edit_message(
            message,
            _("⚠ РП-команда «%s» не найдена") % name
        )
    await RolePlayCommandTemp.load_from_db()
