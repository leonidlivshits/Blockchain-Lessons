import json
import os
from decimal import Decimal, InvalidOperation
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit

from eth_account import Account
from web3 import Web3
from web3.exceptions import TimeExhausted

from network_config import EXPECTED_CHAIN_IDS


def load_keystore(name):
    path = Path(__file__).with_name(f"{name}.json")
    try:
        keystore = json.loads(path.read_text(encoding="utf-8"))
        address = keystore["address"]
        if not isinstance(address, str):
            raise ValueError("Неверный адрес")
        if not address.startswith("0x"):
            address = "0x" + address
        return keystore, Web3.to_checksum_address(address)
    except (OSError, KeyError, TypeError, ValueError):
        raise SystemExit(f"Не удалось прочитать {path.name}") from None


def main():
    rpc_url = os.getenv("ETH_SEPOLIA_RPC", "").strip()
    if not rpc_url:
        rpc_url = getpass("Введите Sepolia RPC URL (ввод скрыт): ").strip()

    parsed_url = urlsplit(rpc_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise SystemExit("Нужен полный HTTP(S) RPC URL для Sepolia.")

    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
    try:
        if not web3.is_connected():
            raise SystemExit("Нет подключения к Sepolia RPC.")
        chain_id = web3.eth.chain_id
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(f"Ошибка подключения к RPC ({type(error).__name__}).") from None

    if chain_id != EXPECTED_CHAIN_IDS["Sepolia"]:
        raise SystemExit(f"Неверная сеть: получен Chain ID {chain_id}, нужен Sepolia.")

    keystore_1, address_1 = load_keystore("address_1")
    _, address_2 = load_keystore("address_2")
    if address_1 == address_2:
        raise SystemExit("Адреса отправителя и получателя совпадают.")

    amount_text = input("Сколько Sepolia ETH отправить с address_1 на address_2? ").strip()
    try:
        amount_eth = Decimal(amount_text)
    except InvalidOperation:
        raise SystemExit(
            f"Не удалось распознать сумму {amount_text!r}. Введите число, например 0.01."
        ) from None

    if not amount_eth.is_finite() or amount_eth <= 0:
        raise SystemExit("Сумма должна быть положительным конечным числом.")

    try:
        value_wei = Web3.to_wei(amount_eth, "ether")
    except ValueError as error:
        raise SystemExit(f"Не удалось преобразовать {amount_eth} ETH в Wei: {error}") from None
    if value_wei <= 0:
        raise SystemExit("Сумма меньше 1 Wei.")

    try:
        latest_block = web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        priority_fee = web3.eth.max_priority_fee
        max_fee = base_fee * 2 + priority_fee
        nonce = web3.eth.get_transaction_count(address_1, "pending")
        balance_wei = web3.eth.get_balance(address_1)
        estimated_gas = web3.eth.estimate_gas(
            {"from": address_1, "to": address_2, "value": value_wei}
        )
    except Exception as error:
        raise SystemExit(f"Ошибка получения баланса или комиссии ({type(error).__name__}).") from None

    gas_limit = (estimated_gas * 12 + 9) // 10
    max_total_wei = value_wei + gas_limit * max_fee
    print(f"Сеть: Sepolia (Chain ID {chain_id})")
    print(f"Отправитель: {address_1}")
    print(f"Получатель: {address_2}")
    print(f"Сумма: {amount_eth} ETH")
    print(f"Баланс отправителя: {Web3.from_wei(balance_wei, 'ether')} ETH")
    print(f"Оценка газа: {estimated_gas}; лимит с запасом: {gas_limit}")
    print(f"Предельная комиссия: {Web3.from_wei(gas_limit * max_fee, 'ether')} ETH")
    if max_total_wei > balance_wei:
        raise SystemExit("Недостаточно Sepolia ETH для суммы и предельной комиссии.")

    if input("Для отправки введите ОТПРАВИТЬ: ").strip() != "ОТПРАВИТЬ":
        raise SystemExit("Отправка отменена.")

    password = getpass("Пароль от address_1.json: ")
    try:
        private_key = Account.decrypt(keystore_1, password)
        if Account.from_key(private_key).address != address_1:
            raise SystemExit("Ключ в address_1.json не соответствует адресу отправителя.")
    except (ValueError, TypeError):
        raise SystemExit("Не удалось расшифровать address_1.json. Проверьте пароль.") from None

    transaction = {
        "chainId": chain_id,
        "nonce": nonce,
        "to": address_2,
        "value": value_wei,
        "gas": gas_limit,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
        "type": 2,
    }

    signed = Account.sign_transaction(transaction, private_key)
    tx_hash = signed.hash
    tx_hash_hex = Web3.to_hex(tx_hash)
    print(f"Transaction ID подписанной транзакции: {tx_hash_hex}")
    print(f"Sepolia Etherscan: https://sepolia.etherscan.io/tx/{tx_hash_hex}")
    try:
        web3.eth.send_raw_transaction(signed.raw_transaction)
    except Exception as error:
        raise SystemExit(
            f"RPC не подтвердил отправку ({type(error).__name__}). "
            "Сначала проверьте транзакцию по ссылке выше; не запускайте перевод повторно вслепую."
        ) from None

    print("RPC подтвердил прием транзакции.")

    try:
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    except TimeExhausted:
        print("Транзакция отправлена, подтверждение пока не получено. Проверьте ссылку выше.")
        return
    except Exception as error:
        print(f"Не удалось проверить подтверждение ({type(error).__name__}). Проверьте ссылку выше.")
        return

    if receipt["status"] == 1:
        print(f"Подтверждено в блоке {receipt['blockNumber']}; газ: {receipt['gasUsed']}.")
    else:
        raise SystemExit(
            f"Транзакция завершилась с ошибкой (статус {receipt['status']}, "
            f"газ {receipt['gasUsed']} из {gas_limit}). Проверьте ссылку выше."
        )


if __name__ == "__main__":
    main()
