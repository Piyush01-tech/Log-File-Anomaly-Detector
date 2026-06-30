import time
import sys
from pathlib import Path
from multiprocessing import Pool, cpu_count

sys.path.append(str(Path(__file__).parent.parent))
import Evtx.Evtx as evtx
from ml_engine.parser import EVTXRecordParser

def parse_worker(args):
    file_path, worker_id, num_workers, tactic, source_file = args
    parser = EVTXRecordParser(tactic=tactic, source_file=source_file)
    results = []
    
    with evtx.Evtx(str(file_path)) as log:
        for i, record in enumerate(log.records()):
            if i % num_workers == worker_id:
                try:
                    xml_str = record.xml()
                    parsed = parser.parse(xml_str)
                    if parsed:
                        results.append(parsed)
                except Exception:
                    pass
    return results

def benchmark5():
    file_path = Path("web_dashboard/mediafiles/evtx_uploads/9be3a55fd7ac_CA_PetiPotam_etw_rpc_efsr_5_6.evtx")
    
    t0 = time.time()
    num_workers = min(cpu_count(), 8)
    args_list = [(file_path, i, num_workers, "tactic", "source_file") for i in range(num_workers)]
    
    with Pool(num_workers) as pool:
        results = pool.map(parse_worker, args_list)
        
    all_records = []
    for r in results:
        all_records.extend(r)
        
    t1 = time.time()
    print(f"Parsed {len(all_records)} records using {num_workers} workers in {t1 - t0:.4f} seconds")

if __name__ == "__main__":
    benchmark5()
