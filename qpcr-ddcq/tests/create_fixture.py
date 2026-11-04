"""Clearly synthetic acceptance data; never interpreted as laboratory observations."""
import csv
import json
from pathlib import Path

def create(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for group,sample,delta in [('Control','c1',4),('Control','c2',6),('Treatment long label','t1',3),('Treatment long label','t2',3),('Missing','m1',None)]:
        for gene,mean in [('GAPDH',20),('FLG',None if delta is None else 20+delta),('TJP1',None if delta is None else 18+delta)]:
            for tech in range(2):
                if sample=='t2' and gene=='GAPDH':continue
                shift=(-.1 if tech==0 else .1)
                if sample=='t1' and gene=='FLG':shift=(-.25 if tech==0 else .25)
                if sample=='t1' and gene=='TJP1':shift=(-.5 if tech==0 else .5)
                cq='Undetermined' if mean is None else mean+shift
                rows.append({'Group':group,'Sample':sample,'Bio':sample,'Gene':gene,'Cq':cq,'Well':str(len(rows)+1),'Excluded':False,'Kind':'sample','Instrument Ratio':'ignored'})
    rows.append(dict(rows[0],Cq=35,Well='excluded',Excluded=True))
    with (root/'synthetic.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    config={'inputs':[{'path':'synthetic.csv','run':'synthetic-plate','scope':'synthetic','columns':{'group':'Group','sample':'Sample','bio_id':'Bio','gene':'Gene','cq_raw':'Cq','well':'Well','excluded_raw':'Excluded','kind':'Kind'}}],
            'params':{'biological_replicates':True,'targets':['FLG','TJP1'],'error_bar':'SD'},'output_dir':'result'}
    (root/'analysis-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    return root/'analysis-config.json'

if __name__=='__main__':
    import sys
    print(create(sys.argv[1]))
