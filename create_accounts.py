import json
from getpass import getpass
from pathlib import Path
from eth_account import Account

password = getpass("Пароль для ключей: ")
if not password or password != getpass("Повтори пароль: "):
    raise SystemExit("Пустой пароль или пароли не совпадают")

folder = Path.home() / "ethereum-course-keys"
folder.mkdir(exist_ok=True)

for name in ("address_1", "address_2"):
    account = Account.create()
    encrypted_key = Account.encrypt(account.key, password)

    with (folder / f"{name}.json").open("x", encoding="utf-8") as file:
        json.dump(encrypted_key, file)

    print(f"{name}: {account.address}")