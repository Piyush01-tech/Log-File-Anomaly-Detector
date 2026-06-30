import time
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import Evtx.Evtx as evtx

def benchmark4():
    file_path = Path("web_dashboard/mediafiles/evtx_uploads/9be3a55fd7ac_CA_PetiPotam_etw_rpc_efsr_5_6.evtx")
    
    t0 = time.time()
    count = 0
    with evtx.Evtx(str(file_path)) as log:
        for record in log.records():
            count += 1
    t1 = time.time()
    print(f"Iterated {count} records in {t1 - t0:.4f} seconds")

if __name__ == "__main__":
    benchmark4()
