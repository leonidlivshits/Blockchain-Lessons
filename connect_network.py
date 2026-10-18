import json
import os
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit

from network_config import EXPECTED_CHAIN_IDS


def load_address_1(web3):
    path = Path(__file__).with_name("address_1.json")
    if not path.is_file():
        raise SystemExit(f"Не найден {path.name}")

    try:
        address = json.loads(path.read_text(encoding="utf-8"))["address"]
        if not isinstance(address, str):
            raise ValueError("Неверный формат адреса")
        if not address.startswith("0x"):
            address = "0x" + address
        return web3.to_checksum_address(address)
    except (OSError, KeyError, ValueError, TypeError):
        raise SystemExit("Не удалось прочитать адрес из address_1.json") from None


def main():
    print("1 - Ethereum Mainnet")
    print("2 - Sepolia")
    print("3 - Hoodi")
    print("4 - Ganache")

    choice = input("Выберите сеть (1-4): ").strip()

    if choice == "1":
        network = "Ethereum Mainnet"
        env_name = "ETH_MAINNET_RPC"
    elif choice == "2":
        network = "Sepolia"
        env_name = "ETH_SEPOLIA_RPC"
    elif choice == "3":
        network = "Hoodi"
        env_name = "ETH_HOODI_RPC"
    elif choice == "4":
        network = "Ganache"
        env_name = "GANACHE_RPC"
    else:
        raise SystemExit("Нужно выбрать число от 1 до 4.")

    expected_chain_id = EXPECTED_CHAIN_IDS[network]

    rpc_url = os.getenv(env_name, "").strip()
    if not rpc_url:
        if choice == "4":
            rpc_url = input("RPC URL Ganache [http://127.0.0.1:7545]: ").strip()
            rpc_url = rpc_url or "http://127.0.0.1:7545"
        else:
            rpc_url = getpass(f"Введите RPC URL для {network} (ввод скрыт): ").strip()

    parsed_url = urlsplit(rpc_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise SystemExit("Нужен полный HTTP(S) RPC URL.")

    try:
        from web3 import Web3
    except ImportError:
        raise SystemExit("Установите web3") from None

    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
    try:
        if not web3.is_connected():
            raise SystemExit("Нет подключения")
        actual_chain_id = web3.eth.chain_id
        block_number = web3.eth.block_number
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(
            f"Ошибка RPC ({type(error).__name__}). Проверьте адрес и доступность сети."
        ) from None

    if expected_chain_id is not None and actual_chain_id != expected_chain_id:
        raise SystemExit(
            f"Неверная сеть: ожидался Chain ID {expected_chain_id}, получен {actual_chain_id}."
        )

    print(f"Подключено к {network}")
    print(f"Chain ID: {actual_chain_id}")
    print(f"Последний блок: {block_number}")

    address_1 = load_address_1(web3)
    try:
        block = web3.eth.get_block(block_number)
        balance_wei = web3.eth.get_balance(address_1)
    except Exception as error:
        raise SystemExit(f"Ошибка чтения данных блокчейна ({type(error).__name__}).") from None

    block_time = datetime.fromtimestamp(block["timestamp"], tz=timezone.utc)
    print(f"Блок #{block['number']}")
    print(f"Хеш блока: {block['hash'].hex()}")
    print(f"Время блока (UTC): {block_time.isoformat()}")
    print(f"Транзакций в блоке: {len(block['transactions'])}")
    print(f"Текущий баланс address_1 в сети {network} ({address_1}): {balance_wei} Wei")
    print(f"Баланс в ETH: {web3.from_wei(balance_wei, 'ether')}")


if __name__ == "__main__":
    main()
