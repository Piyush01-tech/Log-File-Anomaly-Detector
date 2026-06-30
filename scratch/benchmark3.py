import time
import sys
import re
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import Evtx.Evtx as evtx
import xml.etree.ElementTree as ET
from ml_engine.parser import EVTXRecordParser

# regex patterns
_EVENT_ID_RE = re.compile(r'<EventID[^>]*>(\d+)</EventID>')
_TIME_RE = re.compile(r'<TimeCreated\s+SystemTime="([^"]+)"')
_COMPUTER_RE = re.compile(r'<Computer>([^<]+)</Computer>')
_CHANNEL_RE = re.compile(r'<Channel>([^<]+)</Channel>')
_PROVIDER_RE = re.compile(r'<Provider\s+Name="([^"]+)"')

def extract_data_re(xml_str):
    res = {}
    
    # Example to get data elements
    for match in re.finditer(r'<Data\s+Name="([^"]+)">([^<]*)</Data>', xml_str):
        res[match.group(1)] = match.group(2)
    return res

def fast_parse(xml_str):
    event_id = _EVENT_ID_RE.search(xml_str)
    event_id = int(event_id.group(1)) if event_id else None
    
    time = _TIME_RE.search(xml_str)
    time = time.group(1) if time else ""
    
    computer = _COMPUTER_RE.search(xml_str)
    computer = computer.group(1) if computer else ""
    
    channel = _CHANNEL_RE.search(xml_str)
    channel = channel.group(1) if channel else ""
    
    data = extract_data_re(xml_str)
    return {
        "event_id": event_id,
        "time": time,
        "computer": computer,
        "channel": channel,
        "data": data
    }

def benchmark3():
    file_path = Path("web_dashboard/mediafiles/evtx_uploads/9be3a55fd7ac_CA_PetiPotam_etw_rpc_efsr_5_6.evtx")
    
    xml_strings = []
    print("Reading 2000 records...")
    t0 = time.time()
    with evtx.Evtx(str(file_path)) as log:
        for i, record in enumerate(log.records()):
            if i >= 2000: break
            xml_strings.append(record.xml())
    print(f"Read 2000 XML strings in {time.time()-t0:.4f}s")
    
    print("Parsing with current parser...")
    t0 = time.time()
    old_parser = EVTXRecordParser()
    for xml_str in xml_strings:
        old_parser.parse(xml_str)
    print(f"Current parser: {time.time()-t0:.4f}s")
    
    print("Parsing with regex parser...")
    t0 = time.time()
    for xml_str in xml_strings:
        fast_parse(xml_str)
    print(f"Regex parser: {time.time()-t0:.4f}s")

if __name__ == "__main__":
    benchmark3()
