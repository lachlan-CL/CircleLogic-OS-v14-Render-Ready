"""Optional single-node polling worker. Run separately from the web process."""
import argparse
import time
from .config import Settings
from .db import Store
from .security import Vault
from .services import perform_sync
from .connectors import ConnectorError

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--interval',type=int,default=900)
    args=parser.parse_args()
    settings=Settings.load();store=Store(settings.database);vault=Vault(settings.vault_key)
    while True:
        connections=store.all("SELECT * FROM connections WHERE credentials IS NOT NULL AND status IN ('connected','error','authorised')")
        for connection in connections:
            try:
                perform_sync(store,vault,connection,'system')
            except ConnectorError:
                pass  # Sanitised failure is already recorded per tenant in the audit table.
        if args.once:
            return
        time.sleep(max(300,args.interval))

if __name__=='__main__':
    main()
