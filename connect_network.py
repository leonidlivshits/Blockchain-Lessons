import os
from getpass import getpass
from urllib.parse import urlsplit

from network_config import EXPECTED_CHAIN_IDS


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


if __name__ == "__main__":
    main()
