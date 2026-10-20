"""검토 큐 DOI의 공식 공개 본문 접근성을 대조한다. 학습 승인은 하지 않는다."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from fetch_wt_expansion import fetch_one

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data/interim/main_cohort_inventory_20261020/source_priority_queue.csv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/raw/protocol_discovery_20261020")
    parser.add_argument("--max-fulltexts", type=int, default=5)
    args = parser.parse_args()
    out = ROOT / args.output_dir
    if out.exists():
        raise FileExistsError(f"기존 결과 보호: {out}")
    out.mkdir(parents=True)
    with QUEUE.open() as f:
        queue = list(csv.DictReader(f))
    dois = list(dict.fromkeys(r['doi'].lower() for r in queue if r['doi']))
    sources, indexed = [], {}

    def save_manifest():
        (out/'manifest.json').write_text(json.dumps({
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'inputs_sha256': {str(QUEUE.relative_to(ROOT)): digest(QUEUE), str(Path(__file__).relative_to(ROOT)): digest(Path(__file__))},
            'query_dois': len(dois), 'queue_assays': len(queue),
            'training_approved': False, 'model_training_executed': False,
            'sources': sources,
        }, ensure_ascii=False, indent=2)+'\n')

    for start in range(0, len(dois), 20):
        batch = dois[start:start+20]
        query = ' OR '.join('DOI:"'+doi+'"' for doi in batch)
        url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query':query, 'format':'json','resultType':'core','pageSize':1000})
        record = fetch_one((f'index_{start//20:02d}.json',url,'json'),out)
        sources.append(record)
        save_manifest()
        if not record.get('content_candidate'):
            raise RuntimeError('공식 색인 응답을 확보하지 못해 중단: 네트워크/응답 상태 확인 필요')
        response = json.loads((ROOT/record['path']).read_text())
        assert response['hitCount'] <= 1000, '색인 페이지 누락 위험'
        for item in response['resultList']['result']:
            doi=item.get('doi','').lower()
            if doi in batch:
                indexed[doi]=item
        time.sleep(.25)

    result=[]
    for row in queue:
        item=indexed.get(row['doi'].lower(),{})
        result.append({**row, 'epmc_index_match':bool(item), 'pmcid':item.get('pmcid',''),
                       'epmc_inPMC':item.get('inPMC',''), 'epmc_isOpenAccess':item.get('isOpenAccess',''),
                       'epmc_hasSuppl':item.get('hasSuppl',''), 'primary_fulltext_obtained':False})

    # 이미 확보한 본문 대신 아직 검토하지 않은 공개 XML을 우선한다.
    existing_pmc=set()
    for d in (ROOT/'data/raw').iterdir():
        if d.is_dir():
            for f in d.glob('PMC*.*'):
                if f.suffix in ('.html','.xml') and f.stat().st_size>15000:
                    existing_pmc.add(f.stem)
    selected=[]
    ranked=sorted(result, key=lambda r:(r['variant_screen']!='WT', 'human' not in r['description'].lower(), -int(r['connectivity_groups'])))
    for row in ranked:
        pmcid=row['pmcid']
        if not pmcid or row['epmc_isOpenAccess']!='Y' or pmcid in selected or pmcid in existing_pmc:
            continue
        if len(selected)>=args.max_fulltexts:
            break
        selected.append(pmcid)
        record=fetch_one((pmcid+'.xml',f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML','xml'),out)
        if record.get('path') and record.get('http_status')==200:
            try:
                tree=ET.fromstring((ROOT/record['path']).read_bytes())
                article_dois={e.text.lower() for e in tree.findall('.//article-id[@pub-id-type="doi"]') if e.text}
                record['XML_article_DOI_matches']=row['doi'].lower() in article_dois
                record['content_candidate']=tree.tag=='article' and record['XML_article_DOI_matches']
            except ET.ParseError:
                record['content_candidate']=False
        sources.append(record)
        save_manifest()
        for candidate in result:
            if candidate['pmcid']==pmcid:
                candidate['primary_fulltext_obtained']=bool(record.get('content_candidate'))
        time.sleep(.25)
    csvpath=out/'availability_by_assay.csv'
    with csvpath.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    save_manifest()
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['outputs_sha256']={'availability_by_assay.csv':digest(csvpath)}
    manifest['summary']={'indexed_DOIs':len(indexed),'OA_PMCIDs':len({r['pmcid'] for r in result if r['pmcid'] and r['epmc_isOpenAccess']=='Y'}),'new_fulltext_files':sum(bool(s.get('content_candidate')) for s in sources if s.get('name','').endswith('.xml'))}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest['summary'],ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
