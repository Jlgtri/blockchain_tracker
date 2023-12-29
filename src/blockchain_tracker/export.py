from contextlib import suppress
from logging import getLogger
from re import compile
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types.inline_keyboard_button import InlineKeyboardButton as IKB
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup as IKM
from aiogram.types.message import Message
from anyio import sleep as asleep

from .models.public.transactions.transaction import Transaction

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


def _escape(text: str, /) -> str:
    return _markdownV2.sub(lambda m: '\\' + m.group(0), text)


async def export_transaction(
    bot: Bot,
    /,
    transaction: Transaction,
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

    def get_token_address_url(address: str, /) -> str:
        with suppress(ValueError):
            return Transaction.token_address_url(transaction.token_address)

    text = '\n'.join(
        _
        for _ in (
            '{} • {}'.format(
                _escape(transaction.wallet.host.name),
                _escape(transaction.token.chain),
            ),
            '{} от [{}]({}){}'.format(
                'Отправлено'
                if transaction.wallet_address == transaction.from_address
                else 'Получено',
                _escape(Transaction.shorten(transaction.from_address)),
                Transaction.address_url(transaction.from_address),
                ' • {}'.format(_escape(transaction.wallet.name))
                if transaction.wallet_address == transaction.from_address
                else '',
            ),
            *(
                '{} {} на [{}]({}){}'.format(
                    _escape(transaction.token.format_amount(amount.amount)),
                    '[{}]({})'.format(
                        _escape(transaction.token.symbol),
                        get_token_address_url(transaction.token_address) or '',
                    )
                    if transaction.token_address
                    else _escape(transaction.token.symbol),
                    _escape(Transaction.shorten(amount.to_address)),
                    Transaction.address_url(amount.to_address),
                    ' • {}'.format(_escape(transaction.wallet.name))
                    if amount.to_address == transaction.wallet_address
                    else '',
                )
                for amount in sorted(
                    transaction.amounts,
                    key=lambda amount: int(
                        amount.to_address == transaction.wallet_address
                    ),
                    reverse=True,
                )
            ),
            '',
            'Дата транзакции: _%s_'
            % _escape(
                transaction.timestamp.strftime(r'%Y-%m-%d %H:%M:%S UTC')
            ),
        )
        if _ is not None
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
