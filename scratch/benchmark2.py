import time
import sys
from pathlib import Path
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from ml_engine.parser import EVTXFileParser
from ml_engine.feature_engineering import EventFeatureBuilder

def benchmark2():
    file_path = Path("web_dashboard/mediafiles/evtx_uploads/9be3a55fd7ac_CA_PetiPotam_etw_rpc_efsr_5_6.evtx")
    print(f"Benchmarking with {file_path}")
    
    t0 = time.time()
    parser = EVTXFileParser()
    df = parser.parse(file_path)
    t1 = time.time()
    print(f"Time to parse EVTX (Pandas DF): {t1 - t0:.4f} seconds")
    print(f"Total events: {len(df)}")
    
    t2 = time.time()
    builder = EventFeatureBuilder()
    features_df = builder.build(df)
    t3 = time.time()
    print(f"Time to build features: {t3 - t2:.4f} seconds")

if __name__ == "__main__":
    benchmark2()
