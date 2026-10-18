"""Deploy CourseToken from address_2 and transfer 10 CRS on Sepolia."""

import argparse
import json
import os
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit

from eth_account import Account
from web3 import Web3
from web3.exceptions import TimeExhausted

from network_config import EXPECTED_CHAIN_IDS


ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT / "build" / "CourseToken.json"
DEPLOYMENT = ROOT / "erc20_deployment.json"
RECIPIENT = Web3.to_checksum_address("0x80773c866332a7f3CFdD583d0b3A96655F035d6C")
CHAIN_ID = EXPECTED_CHAIN_IDS["Sepolia"]


def connect_sepolia():
    rpc_url = os.getenv("ETH_SEPOLIA_RPC", "").strip()
    if not rpc_url:
        rpc_url = getpass("Введите Sepolia RPC URL (ввод скрыт): ").strip()
    parsed = urlsplit(rpc_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SystemExit("Нужен полный HTTP(S) RPC URL для Sepolia.")

    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
    try:
        if not web3.is_connected() or web3.eth.chain_id != CHAIN_ID:
            raise SystemExit("RPC недоступен или это не Sepolia (Chain ID 11155111).")
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(f"Ошибка подключения к RPC ({type(error).__name__}).") from None
    return web3


def load_address_2():
    path = ROOT / "address_2.json"
    try:
        keystore = json.loads(path.read_text(encoding="utf-8"))
        raw_address = keystore["address"]
        if not raw_address.startswith("0x"):
            raw_address = "0x" + raw_address
        address = Web3.to_checksum_address(raw_address)
    except (OSError, KeyError, TypeError, ValueError):
        raise SystemExit("Не удалось прочитать address_2.json рядом со скриптом.") from None
    return keystore, address


def load_artifact():
    try:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        if artifact["contractName"] != "CourseToken":
            raise ValueError("Неверный контракт")
        if not artifact["compiler"].startswith("0.8.28+"):
            raise ValueError("Неверная версия компилятора")
        if not artifact["bytecode"].startswith("0x"):
            raise ValueError("Нет байткода")
        return artifact
    except (OSError, KeyError, TypeError, ValueError):
        raise SystemExit("Нет корректного build/CourseToken.json. Запустите npm install и npm run compile:token.") from None


def network_settings(web3, address):
    try:
        confirmed_nonce = web3.eth.get_transaction_count(address, "latest")
        pending_nonce = web3.eth.get_transaction_count(address, "pending")
        if pending_nonce != confirmed_nonce:
            raise SystemExit("У address_2 есть ожидающая транзакция. Дождитесь её подтверждения.")
        latest_block = web3.eth.get_block("latest")
        priority_fee = web3.eth.max_priority_fee
        fees = {
            "maxFeePerGas": latest_block["baseFeePerGas"] * 2 + priority_fee,
            "maxPriorityFeePerGas": priority_fee,
        }
        balance = web3.eth.get_balance(address)
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(f"Ошибка чтения Sepolia ({type(error).__name__}).") from None
    return pending_nonce, fees, balance


def send_transaction(web3, keystore, address, transaction, balance, confirmation):
    try:
        estimate_input = {key: value for key, value in transaction.items() if key != "gas"}
        estimated_gas = web3.eth.estimate_gas(estimate_input)
    except Exception as error:
        raise SystemExit(f"Не удалось оценить газ ({type(error).__name__}).") from None
    transaction["gas"] = (estimated_gas * 12 + 9) // 10
    max_cost = transaction.get("value", 0) + transaction["gas"] * transaction["maxFeePerGas"]
    print(f"Оценка газа: {estimated_gas}; лимит с запасом: {transaction['gas']}")
    print(f"Предельная комиссия: {Web3.from_wei(max_cost, 'ether')} Sepolia ETH")
    if max_cost > balance:
        raise SystemExit("На address_2 недостаточно Sepolia ETH для предельной комиссии.")
    if input(f"Для продолжения введите {confirmation}: ").strip() != confirmation:
        raise SystemExit("Операция отменена.")

    password = getpass("Пароль от address_2.json: ")
    try:
        private_key = Account.decrypt(keystore, password)
        if Account.from_key(private_key).address != address:
            raise SystemExit("Ключ в address_2.json не соответствует адресу отправителя.")
    except (ValueError, TypeError):
        raise SystemExit("Не удалось расшифровать address_2.json. Проверьте пароль.") from None
    signed = Account.sign_transaction(transaction, private_key)
    tx_hash = Web3.to_hex(signed.hash)
    print(f"Transaction ID подписанной транзакции: {tx_hash}")
    print(f"Sepolia Etherscan: https://sepolia.etherscan.io/tx/{tx_hash}")

    try:
        web3.eth.send_raw_transaction(signed.raw_transaction)
    except Exception as error:
        raise SystemExit(
            f"RPC не подтвердил отправку ({type(error).__name__}). "
            "Проверьте хеш выше перед повторной попыткой."
        ) from None
    print("RPC подтвердил прием транзакции.")

    try:
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    except TimeExhausted:
        raise SystemExit("Транзакция отправлена, но ещё не подтверждена. Проверьте ссылку выше.") from None
    except Exception as error:
        raise SystemExit(
            f"Не удалось проверить подтверждение ({type(error).__name__}). Проверьте ссылку выше."
        ) from None
    if receipt["status"] != 1:
        raise SystemExit(f"Транзакция завершилась с ошибкой. Газ: {receipt['gasUsed']}.")
    print(f"Подтверждено в блоке {receipt['blockNumber']}; газ: {receipt['gasUsed']}.")
    return receipt, tx_hash


def deploy(web3, keystore, address, artifact):
    if DEPLOYMENT.exists():
        raise SystemExit("erc20_deployment.json уже существует. Проверьте развёрнутый контракт.")
    nonce, fees, balance = network_settings(web3, address)
    contract = web3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    transaction = contract.constructor().build_transaction(
        {
            "from": address,
            "chainId": CHAIN_ID,
            "nonce": nonce,
            "value": 0,
            "gas": 8_000_000,
            "type": 2,
            **fees,
        }
    )
    print(f"Сеть: Sepolia; адрес развёртывания: {address}")
    print("Контракт: Course Token (CRS); исходный выпуск: 100 токенов")
    receipt, tx_hash = send_transaction(
        web3, keystore, address, transaction, balance, "РАЗВЕРНУТЬ"
    )
    contract_address = receipt["contractAddress"]
    if not contract_address:
        raise SystemExit("Транзакция подтверждена, но адрес контракта отсутствует.")
    record = {
        "chain_id": CHAIN_ID,
        "contract_address": contract_address,
        "deployment_tx": tx_hash,
        "name": "Course Token",
        "symbol": "CRS",
    }
    DEPLOYMENT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Адрес контракта: {contract_address}")
    print(f"Contract creation transaction ID: {tx_hash}")
    deployed = web3.eth.contract(address=contract_address, abi=artifact["abi"])
    decimals = deployed.functions.decimals().call()
    total_supply = deployed.functions.totalSupply().call()
    owner_balance = deployed.functions.balanceOf(address).call()
    if total_supply != 100 * 10**decimals or owner_balance != total_supply:
        raise SystemExit("Контракт развёрнут, но выпуск или баланс не совпадает с ожидаемым.")
    print(f"Проверено: totalSupply = 100 CRS; баланс address_2 = 100 CRS.")


def transfer(web3, keystore, address, artifact):
    try:
        record = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
        if record["chain_id"] != CHAIN_ID or record["symbol"] != "CRS":
            raise ValueError("Неверная сеть или токен")
        contract_address = Web3.to_checksum_address(record["contract_address"])
        if record.get("transfer_tx"):
            raise SystemExit(f"Перевод уже записан: {record['transfer_tx']}")
    except SystemExit:
        raise
    except (OSError, KeyError, TypeError, ValueError):
        raise SystemExit("Нет корректного erc20_deployment.json. Сначала разверните контракт.") from None

    if not web3.eth.get_code(contract_address):
        raise SystemExit("На адресе контракта нет кода в Sepolia.")
    token = web3.eth.contract(address=contract_address, abi=artifact["abi"])
    try:
        if token.functions.symbol().call() != "CRS":
            raise SystemExit("У контракта другой символ токена.")
        decimals = token.functions.decimals().call()
        if token.functions.totalSupply().call() != 100 * 10**decimals:
            raise SystemExit("Выпуск токена отличается от 100 CRS.")
        amount = 10 * 10**decimals
        if token.functions.balanceOf(address).call() < amount:
            raise SystemExit("На address_2 меньше 10 CRS.")
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(f"Ошибка чтения контракта ({type(error).__name__}).") from None

    nonce, fees, balance = network_settings(web3, address)
    transaction = token.functions.transfer(RECIPIENT, amount).build_transaction(
        {
            "from": address,
            "chainId": CHAIN_ID,
            "nonce": nonce,
            "value": 0,
            "gas": 8_000_000,
            "type": 2,
            **fees,
        }
    )
    print(f"Сеть: Sepolia; токен: {contract_address}")
    print(f"Отправитель: {address}; получатель: {RECIPIENT}; сумма: 10 CRS")
    receipt, tx_hash = send_transaction(
        web3, keystore, address, transaction, balance, "ПЕРЕВЕСТИ"
    )
    transfers = token.events.Transfer().process_receipt(receipt)
    if not any(
        event["args"]["from"] == address
        and event["args"]["to"] == RECIPIENT
        and event["args"]["value"] == amount
        for event in transfers
    ):
        raise SystemExit("Транзакция подтверждена, но событие перевода 10 CRS не найдено.")
    record["transfer_tx"] = tx_hash
    DEPLOYMENT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Token transfer transaction ID: {tx_hash}")


def main():
    parser = argparse.ArgumentParser(description="ERC-20 на Sepolia от address_2")
    parser.add_argument("action", choices=("deploy", "transfer"))
    args = parser.parse_args()
    artifact = load_artifact()
    web3 = connect_sepolia()
    keystore, address = load_address_2()
    if args.action == "deploy":
        deploy(web3, keystore, address, artifact)
    else:
        transfer(web3, keystore, address, artifact)


if __name__ == "__main__":
    main()
