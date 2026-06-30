import time
import sys
from pathlib import Path

# Adjust path to find ml_engine
sys.path.append(str(Path(__file__).parent.parent))
from ml_engine.parser import EVTXFileParser, EVTXRecordParser
import Evtx.Evtx as evtx
import xml.etree.ElementTree as ET

def benchmark():
    # Find a test file
    evtx_dir = Path("data/raw_logs")
    evtx_files = list(evtx_dir.rglob("*.evtx"))
    if not evtx_files:
        print("No .evtx files found for benchmark.")
        return
    
    file_path = evtx_files[0]
    print(f"Benchmarking with {file_path} (size: {file_path.stat().st_size / 1024 / 1024:.2f} MB)")
    
    parser = EVTXRecordParser()
    
    # 1. Measure pure python-evtx reading + xml generation
    t0 = time.time()
    xml_strings = []
    with evtx.Evtx(str(file_path)) as log:
        for i, record in enumerate(log.records()):
            if i >= 10000:
                break
            xml_strings.append(record.xml())
    t1 = time.time()
    print(f"Time to read 10000 records and generate XML: {t1 - t0:.4f} seconds")
    
    # 2. Measure ElementTree parsing
    t2 = time.time()
    for xml_str in xml_strings:
        try:
            root = ET.fromstring(xml_str)
        except:
            pass
    t3 = time.time()
    print(f"Time to ET.fromstring 10000 records: {t3 - t2:.4f} seconds")
    
    # 3. Measure full parser
    t4 = time.time()
    for xml_str in xml_strings:
        parser.parse(xml_str)
    t5 = time.time()
    print(f"Time for full EVTXRecordParser.parse on 10000 records: {t5 - t4:.4f} seconds")

if __name__ == "__main__":
    benchmark()
