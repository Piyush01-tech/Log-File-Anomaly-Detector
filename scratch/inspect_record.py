import time
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import Evtx.Evtx as evtx

def inspect():
    file_path = Path("web_dashboard/mediafiles/evtx_uploads/9be3a55fd7ac_CA_PetiPotam_etw_rpc_efsr_5_6.evtx")
    with evtx.Evtx(str(file_path)) as log:
        for record in log.records():
            print(dir(record))
            break

if __name__ == "__main__":
    inspect()
