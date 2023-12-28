from datetime import datetime, timezone
from logging import getLogger
from re import compile
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types.inline_keyboard_button import InlineKeyboardButton as IKB
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup as IKM
from aiogram.types.message import Message
from anyio import sleep as asleep
from dateutil.tz.tz import tzlocal

from .fetch import TransactionData

#
logger = getLogger('Export')
_markdownV2 = compile(
    '|'.join(
        '\\' + _
        for _ in (
            '_',
            '*',
            '[',
            ']',
            '(',
            ')',
            '~',
            '`',
            '>',
            '#',
            '+',
            '-',
            '=',
            '|',
            '{',
            '}',
            '.',
            '!',
        )
    )
)


def _modify(text: str, /) -> str:
    return _markdownV2.sub(lambda m: '\\' + m.group(0), text)


async def export_transaction(
    bot: Bot,
    /,
    transaction: TransactionData,
    chat_id: int,
    *,
    index: Optional[int] = None,
) -> Message:
    logger.info(
        '%sExporting transaction `%s` to chat `%s`...',
        '[%s] ' % index if index is not None else '',
        transaction.hash,
        chat_id,
    )

    text = '\n'.join(
        _
        for _ in (
            '{} от [{}]({}) • {}'.format(
                'Отправлено'
                if transaction.wallet_address == transaction.from_address
                else 'Получено',
                _modify(TransactionData.shorten(transaction.from_address)),
                TransactionData.address_url(transaction.from_address),
                _modify(transaction.chain),
            ),
            *(
                '{} {} на [{}]({})'.format(
                    _modify(transaction.format_amount(amount)),
                    '[%s](%s)'
                    % (
                        _modify(transaction.symbol),
                        TransactionData.token_address_url(
                            transaction.token_address
                        ),
                    )
                    if transaction.token_address
                    else _modify(transaction.symbol),
                    _modify(TransactionData.shorten(address)),
                    TransactionData.address_url(address),
                )
                for address, amount in sorted(
                    transaction.amounts,
                    key=lambda x: int(x[0] == transaction.wallet_address),
                    reverse=True,
                )
            ),
        )
        if _ is not None
    )

    text = '\n'.join(
        (
            text,
            '',
            'Дата транзакции: _%s_'
            % _modify(
                datetime.fromtimestamp(transaction.timestamp, timezone.utc)
                .astimezone(tzlocal())
                .strftime(r'%Y-%m-%d %H:%M:%S')
            ),
        )
    )

    while True:
        try:
            return await bot.send_message(
                chat_id,
                text,
                parse_mode='MarkdownV2',
                reply_markup=IKM(
                    inline_keyboard=[[IKB(text='Ссылка', url=transaction.url)]]
                ),
                disable_web_page_preview=True,
            )
        except TelegramRetryAfter as exception:
            logger.warning(
                '%sFlood wait for `%s` second%s!',
                '[%s] ' % index if index is not None else '',
                exception.retry_after,
                '' if exception.retry_after == 1 else 's',
            )
            await asleep(exception.retry_after)
