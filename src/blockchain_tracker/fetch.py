from datetime import datetime
from json import loads
from logging import getLogger
from re import search, sub
from typing import Final, Iterable, Mapping, Optional, Tuple

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from web3 import Web3

from .models.public.tokens.token import Token
from .models.public.transactions.transaction import Transaction
from .models.public.transactions.transaction_amount import TransactionAmount
from .models.public.wallets.wallet import WalletHost, WalletHostAction

#
logger = getLogger('Fetch')

w3: Final = Web3()
ETHEREUM_TOKENS: Final = {}
ETHEREUM_CONTRACTS: Final = {}


async def fetch_tradersroom_token(
    session: ClientSession,
    /,
    host: WalletHost,
    email: str,
    password: str,
    *,
    index: Optional[int] = None,
) -> Optional[Tuple[str, str]]:
    logger.debug(
        '%sStarted fetching token from `%s` for email `%s` and password `%s`...',
        '[%s] ' % index if index is not None else '',
        host.value,
        email,
        password,
    )
    async with session.post(
        f'https://weboffice.{host.value}/api/v_2/page/Login',
        data=dict(
            savePassword='true',
            user_email=email,
            password=password,
            key=host.key(WalletHostAction.login),
            rand_param=host.rand_param(WalletHostAction.login),
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
                '%sException while fetching token from `%s` for email `%s` and '
                'password `%s`: %s',
                '[%s] ' % index if index is not None else '',
                host.value,
                email,
                password,
                await response.text(),
            )
        data = await response.json()
    try:
        user_id = data['values']['user_id']
        token = data['values']['auth_token']
    except BaseException as _:
        return logger.exception(
            '%sException while fetching token from `%s` for email `%s` and '
            'password `%s`: %s',
            '[%s] ' % index if index is not None else '',
            host.value,
            email,
            password,
            data,
            exc_info=False,
        )
    logger.info(
        '%sFetched user_id `%s` and token `%s` from `%s` for email `%s` and password `%s`!',
        '[%s] ' % index if index is not None else '',
        user_id,
        token,
        host.value,
        email,
        password,
    )
    return user_id, token


async def fetch_tradersroom_wallets(
    session: ClientSession,
    /,
    host: WalletHost,
    user_id: str,
    token: str,
    *,
    index: Optional[int] = None,
) -> Mapping[str, str]:
    logger.debug(
        '%sStarted fetching wallets from `%s` for token `%s`...',
        '[%s] ' % index if index is not None else '',
        host.value,
        token,
    )
    async with session.get(
        f'https://weboffice.{host.value}/api/v_2/payments/GetPaymentSystemsUnitedByGroups',
        params=dict(
            auth_token=token,
            key=host.key(WalletHostAction.fetch_wallets),
            languages='en',
            rand_param=host.rand_param(WalletHostAction.fetch_wallets),
            type='in',
            user_id=user_id,
        ),
        headers={'Accept': 'application/json'},
    ) as response:
        if not response.ok:
            return logger.exception(
                '%sException while fetching wallets from `%s` for token `%s`: %s',
                '[%s] ' % index if index is not None else '',
                host.value,
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
        '%sFetched `%s` wallets from `%s` for token `%s`!',
        '[%s] ' % index if index is not None else '',
        len(wallets),
        host.value,
        token,
    )
    return wallets


async def fetch_bitcoin_wallet_transactions(
    session: ClientSession,
    /,
    wallet_address: str,
    limit: Optional[int] = 20,
    offset: Optional[int] = None,
    *,
    index: Optional[int] = None,
) -> Iterable[Transaction]:
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
                '%sException while fetching transactions for BTC wallet `%s`: %s',
                '[%s] ' % index if index is not None else '',
                wallet_address,
                await response.text(),
            )
        data = await response.json()
    transactions = [
        Transaction(
            hash=tx['hash'],
            wallet_address=wallet_address,
            from_address=tx['inputs'][0]['prev_out']['addr'],
            timestamp=datetime.fromtimestamp(tx['time']),
            token=Token(
                address='bitcoin',
                symbol='BTC',
                name='Bitcoin',
                chain='Bitcoin',
                decimals=8,
            ),
            amounts=[
                TransactionAmount(
                    transaction_hash=tx['hash'],
                    to_address=out['addr'],
                    amount=out['value'],
                )
                for out in tx['out']
            ],
        )
        for tx in reversed(data['txs'])
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
    limit: Optional[int] = 20,
    fingerprint: Optional[str] = None,
    *,
    index: Optional[int] = None,
) -> Iterable[Transaction]:
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
                '%sException while fetching transactions for TRON wallet `%s`: %s',
                '[%s] ' % index if index is not None else '',
                wallet_address,
                await response.text(),
            )
        data = await response.json()
    try:
        transactions = [
            Transaction(
                hash=tx['transaction_id'],
                wallet_address=wallet_address,
                from_address=tx['from'],
                timestamp=datetime.fromtimestamp(tx['block_timestamp'] / 1e3),
                token=(
                    Token(
                        address=tx['token_info']['address'],
                        symbol=tx['token_info']['symbol'],
                        name=tx['token_info']['name'],
                        chain='Tron',
                        decimals=tx['token_info']['decimals'],
                    )
                    if tx['token_info']
                    else Token(
                        address='trx',
                        symbol='TRX',
                        name='TRX (TRON)',
                        chain='Tron',
                        decimals=6,
                    )
                ),
                amounts=[
                    TransactionAmount(
                        transaction_hash=tx['transaction_id'],
                        to_address=tx['to'],
                        amount=int(tx['value']),
                    )
                ],
            )
            for tx in reversed(data['data'])
        ]
    except BaseException as _:
        print()
    logger.info(
        '%sFetched `%s` transactions for TRON wallet `%s`!',
        '[%s] ' % index if index is not None else '',
        len(transactions),
        wallet_address,
    )
    return transactions


async def fetch_ethereum_wallet_transactions(
    session: ClientSession,
    /,
    wallet_address: str,
    apikey: str,
    limit: Optional[int] = 20,
    *,
    index: Optional[int] = None,
) -> Iterable[Transaction]:

    logger.debug(
        '%sStarted fetching transactions for TRON wallet `%s`...',
        '[%s] ' % index if index is not None else '',
        wallet_address,
    )
    async with session.get(
        f'https://api.etherscan.io/api',
        params=dict(
            apikey=apikey,
            offset=limit,
            address=wallet_address,
            module='account',
            action='txlist',
            startblock=0,
            endblock=99999999,
            page=1,
            sort='desc',
        ),
    ) as response:
        if not response.ok:
            return logger.exception(
                '%sException while fetching transactions for '
                'Ethereum wallet `%s`: %s',
                '[%s] ' % index if index is not None else '',
                wallet_address,
                await response.text(),
            )
        data = await response.json()
    transactions = []
    for tx in data['result']:
        if tx['input'] == '0x':
            transactions.append(
                Transaction(
                    hash=tx['hash'],
                    wallet_address=wallet_address,
                    from_address=tx['from'],
                    timestamp=datetime.fromtimestamp(int(tx['timeStamp'])),
                    token=Token(
                        address='0x0000000000000000000000000000000000000000',
                        symbol='ETH',
                        name='Ethereum',
                        chain='Ethereum',
                        decimals=18,
                    ),
                    amounts=[
                        TransactionAmount(
                            transaction_hash=tx['hash'],
                            to_address=tx['to'],
                            amount=int(tx['value']),
                        )
                    ],
                )
            )
            continue

        try:
            if (token := ETHEREUM_TOKENS.get(tx['to'])) is None:
                async with session.get(
                    f'https://api.etherscan.io/api',
                    params=dict(
                        apikey=apikey,
                        contractaddress=tx['to'],
                        module='account',
                        action='tokentx',
                        page=1,
                        offset=1,
                    ),
                ) as response:
                    if not response.ok:
                        logger.exception(
                            '%sException while fetching `tokentx` for '
                            'Ethereum token `%s`: %s',
                            '[%s] ' % index if index is not None else '',
                            tx['to'],
                            await response.text(),
                        )
                        continue
                    data = await response.json()
                token_tx = data['result'][0]
                ETHEREUM_TOKENS[tx['to']] = token = Token(
                    address=tx['to'],
                    symbol=token_tx['tokenSymbol'],
                    name=token_tx['tokenName'],
                    chain='Ethereum',
                    decimals=int(token_tx['tokenDecimal']),
                )

            if (contract := ETHEREUM_CONTRACTS.get(tx['to'])) is None:
                async with session.get(
                    f'https://api.etherscan.io/api',
                    params=dict(
                        apikey=apikey,
                        address=tx['to'],
                        module='contract',
                        action='getabi',
                    ),
                ) as response:
                    if not response.ok:
                        logger.exception(
                            '%sException while fetching `abi` for '
                            'Ethereum token `%s`: %s',
                            '[%s] ' % index if index is not None else '',
                            tx['to'],
                            await response.text(),
                        )
                        continue
                    data = await response.json()
                ETHEREUM_CONTRACTS[tx['to']] = contract = w3.eth.contract(
                    address=w3.to_checksum_address(tx['to']),
                    abi=loads(data['result']),
                )
        except BaseException as _:
            continue

        _object, params = contract.decode_function_input(tx['input'])
        transactions.append(
            Transaction(
                hash=tx['hash'],
                wallet_address=wallet_address,
                from_address=tx['from'],
                timestamp=datetime.fromtimestamp(int(tx['timeStamp'])),
                token=token,
                amounts=[
                    TransactionAmount(
                        transaction_hash=tx['hash'],
                        to_address=params['_to'],
                        amount=int(params['_value']),
                    )
                ],
            )
        )
    logger.info(
        '%sFetched `%s` transactions for Ethereum wallet `%s`!',
        '[%s] ' % index if index is not None else '',
        len(transactions),
        wallet_address,
    )
    return transactions
