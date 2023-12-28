from dataclasses import dataclass
from decimal import Decimal
from logging import getLogger
from math import floor, log10, modf
from re import Pattern, compile, match, search, sub
from typing import ClassVar, Iterable, Mapping, Optional, Self, Tuple, Type

from aiohttp import ClientSession

#
logger = getLogger('Fetch')


@dataclass()
class TransactionData(object):
    hash: str
    wallet_address: str
    from_address: str
    name: str
    symbol: str
    chain: str
    token_address: Optional[str]
    decimals: int
    timestamp: float
    amounts: Iterable[Tuple[str, int]]

    BTC_REGEXP: ClassVar[Pattern] = compile(
        r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$'
    )
    TRON_REGEXP: ClassVar[Pattern] = compile(r'T[A-Za-z1-9]{33}')

    @property
    def url(self: Self, /) -> str:
        if match(self.BTC_REGEXP, self.wallet_address):
            return (
                'https://www.blockchain.com/explorer/transactions/btc/'
                + self.hash
            )
        elif match(self.TRON_REGEXP, self.wallet_address):
            return 'https://tronscan.org/#/transaction/' + self.hash
        else:
            raise ValueError(
                'Wallet address `%s` does not match known explorers!'
                % self.wallet_address
            )

    @classmethod
    def token_address_url(cls: Type[Self], address: str, /) -> str:
        if match(cls.TRON_REGEXP, address):
            return 'https://tronscan.org/#/contract/' + address
        else:
            raise ValueError(
                'Token address `%s` does not match known explorers!' % address
            )

    @classmethod
    def address_url(cls: Type[Self], address: str, /) -> str:
        if match(cls.BTC_REGEXP, address):
            return (
                'https://www.blockchain.com/explorer/addresses/btc/' + address
            )
        elif match(cls.TRON_REGEXP, address):
            return 'https://tronscan.org/#/address/' + address
        else:
            raise ValueError(
                'Wallet address `%s` does not match known explorers!' % address
            )

    @classmethod
    def shorten(cls: Type[Self], address: str, /) -> str:
        if match(cls.BTC_REGEXP, address):
            return address[:4] + '-' + address[-4:]
        elif match(cls.TRON_REGEXP, address):
            return address[:4] + '..' + address[-4:]
        else:
            return address

    def format_amount(self: Self, amount: int, /) -> str:
        return '{:,g}'.format(amount / 10**self.decimals)
        try:
            frac_amount = amount / 10**self.decimals
            digits = -int(floor(log10(abs(modf(frac_amount)[0])))) + 1
            return ('{:,.%sf}' % digits).format(frac_amount)
        except ValueError:
            return '0.' + str(amount).zfill(self.decimals)


async def fetch_tradersroom_token(
    session: ClientSession,
    /,
    email: str,
    password: str,
    *,
    index: Optional[int] = None,
) -> Optional[str]:
    logger.debug(
        '%sStarted fetching token for email `%s` and password `%s`...',
        '[%s] ' % index if index is not None else '',
        email,
        password,
    )
    async with session.post(
        'https://weboffice.whitetrade.net/api/v_2/page/Login',
        data=dict(
            savePassword='true',
            user_email=email,
            password=password,
            # key=''.join(choice(characters) for _ in range(32)),
            # rand_param=randint(int(1e7), int(1e8 - 1)),
            key='434b4a60f39960b0822fc68c51b39b3b',
            rand_param='27320033',
            languages='en',
        ),
        headers={
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,uk;q=0.6',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        },
    ) as response:
        if not response.ok:
            return logger.exception(
                '%sException while fetching token for email `%s` and '
                'password `%s`: %s',
                '[%s] ' % index if index is not None else '',
                email,
                password,
                await response.text(),
            )
        data = await response.json()
    logger.info(
        '%sFetched token `%s` for email `%s` and password `%s`!',
        '[%s] ' % index if index is not None else '',
        token := data['values']['auth_token'],
        email,
        password,
    )
    return token


async def fetch_tradersroom_wallets(
    session: ClientSession,
    /,
    token: str,
    *,
    index: Optional[int] = None,
) -> Mapping[str, str]:
    logger.debug(
        '%sStarted fetching wallets for token `%s`...',
        '[%s] ' % index if index is not None else '',
        token,
    )
    async with session.get(
        f'https://weboffice.whitetrade.net/api/v_2/payments/GetPaymentSystemsUnitedByGroups',
        params=dict(
            auth_token=token,
            key='9e611606476d548ab07ebeb500f0cacf',
            languages='en',
            rand_param='71134563',
            # rand_param=randint(int(1e7), int(1e8 - 1)),
            type='in',
            user_id='157',
        ),
        headers={'Accept': 'application/json'},
    ) as response:
        if not response.ok:
            return logger.exception(
                '%sException while fetching wallets for token `%s`: %s',
                '[%s] ' % index if index is not None else '',
                token,
                await response.text(),
            )
        data = await response.json()
    wallets = {
        item['name']: sub(
            '<.+>',
            '',
            search(
                '<strong>(.+)</strong>',
                item['merchant_description'],
            ).group(1),
        )
        for item in data['values'][0]['method']
    }
    logger.info(
        '%sFetched `%s` wallets for token `%s`!',
        '[%s] ' % index if index is not None else '',
        len(wallets),
        token,
    )
    return wallets


async def fetch_bitcoin_wallet_transactions(
    session: ClientSession,
    /,
    wallet_address: str,
    limit: Optional[int] = 200,
    offset: Optional[int] = None,
    *,
    index: Optional[int] = None,
) -> Iterable[TransactionData]:
    logger.debug(
        '%sStarted fetching transactions for BTC wallet `%s`...',
        '[%s] ' % index if index is not None else '',
        wallet_address,
    )
    async with session.get(
        f'https://blockchain.info/rawaddr/{wallet_address}',
        params=dict(limit=limit, offset=offset or 0),
        headers={'Accept': 'application/json'},
    ) as response:
        if not response.ok:
            return logger.exception(
                '%sException while transactions for BTC wallet `%s`: %s',
                '[%s] ' % index if index is not None else '',
                wallet_address,
                await response.text(),
            )
        data = await response.json()
    transactions = [
        TransactionData(
            wallet_address=wallet_address,
            hash=tx['hash'],
            from_address=tx['inputs'][0]['prev_out']['addr'],
            symbol='BTC',
            token_address=None,
            decimals=8,
            name='Bitcoin',
            chain='Bitcoin',
            timestamp=tx['time'],
            amounts=[(out['addr'], out['value']) for out in tx['out']],
        )
        for tx in data['txs']
    ]
    logger.info(
        '%sFetched `%s` transactions for BTC wallet `%s`!',
        '[%s] ' % index if index is not None else '',
        len(transactions),
        wallet_address,
    )
    return transactions


async def fetch_tron_wallet_transactions(
    session: ClientSession,
    /,
    wallet_address: str,
    limit: Optional[int] = 200,
    fingerprint: Optional[str] = None,
    *,
    index: Optional[int] = None,
) -> Iterable[TransactionData]:
    logger.debug(
        '%sStarted fetching transactions for TRON wallet `%s`...',
        '[%s] ' % index if index is not None else '',
        wallet_address,
    )
    async with session.get(
        f'https://api.trongrid.io/v1/accounts/{wallet_address}/transactions/trc20',
        params=dict(limit=limit)
        | (dict(fingerprint=fingerprint) if fingerprint else {}),
        headers={'Accept': 'application/json'},
    ) as response:
        if not response.ok:
            return logger.exception(
                '%sException while transactions for TRON wallet `%s`: %s',
                '[%s] ' % index if index is not None else '',
                wallet_address,
                await response.text(),
            )
        data = await response.json()
    transactions = [
        TransactionData(
            wallet_address=wallet_address,
            hash=tx['transaction_id'],
            from_address=tx['from'],
            symbol=tx['token_info']['symbol'],
            token_address=tx['token_info']['address'],
            decimals=tx['token_info']['decimals'],
            name=tx['token_info']['name'],
            chain='Tron',
            timestamp=tx['block_timestamp'] / 1e3,
            amounts=[(tx['to'], int(tx['value']))],
        )
        for tx in data['data']
    ]
    logger.info(
        '%sFetched `%s` transactions for TRON wallet `%s`!',
        '[%s] ' % index if index is not None else '',
        len(transactions),
        wallet_address,
    )
    return transactions
