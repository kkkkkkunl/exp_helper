"""Formula-owned six-sheet XLSX output, native charts and static validation."""
from __future__ import annotations
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
from core import ERRORS, json_ready

SHEETS=['说明','原始数据','复孔质控','计算过程','整理数据','作图']


def ref(sheet,col,row):
    from xlsxwriter.utility import xl_col_to_name
    return "'%s'!%s%d" % (sheet.replace("'","''"),xl_col_to_name(col),row+1)


def aggregate(name,refs):
    if not refs:return '0' if name in ('COUNT','SUM') else '""'
    if len(refs)>200:
        chunks=[aggregate(name,refs[i:i+200]) for i in range(0,len(refs),200)]
        if name=='COUNT':return 'SUM('+','.join(chunks)+')'
        if name in ('MAX','MIN','SUM'):return name+'('+','.join(chunks)+')'
        raise ValueError('单个分析单元超过200个重复，请按明确范围拆分')
    return name+'('+','.join(refs)+')'


def build(model,path,provenance):
    import xlsxwriter
    wb=xlsxwriter.Workbook(str(path),{'strings_to_formulas':False,'strings_to_urls':False})
    wb.set_properties({'title':'qPCR relative expression','comments':'Formula-owned values; see verification manifest.'})
    wb.set_calc_mode('auto')
    fonts={'font_name':'Microsoft YaHei','font_size':10,'valign':'vcenter'}
    normal=wb.add_format(fonts); num=wb.add_format(dict(fonts,num_format='0.000'))
    integer=wb.add_format(dict(fonts,num_format='0'))
    head=wb.add_format(dict(fonts,bold=True,bg_color='#334155',font_color='#FFFFFF',text_wrap=True))
    wrap=wb.add_format(dict(fonts,text_wrap=True,valign='top'))
    green=wb.add_format(dict(fonts,bg_color='#DCFCE7',font_color='#166534'))
    orange=wb.add_format(dict(fonts,bg_color='#FFEDD5',font_color='#9A3412'))
    red=wb.add_format(dict(fonts,bg_color='#FEE2E2',font_color='#991B1B'))
    ws={name:wb.add_worksheet(name) for name in SHEETS}
    def table(name,headers,width=18):
        w=ws[name];w.hide_gridlines(2);w.set_default_row(22)
        w.set_column(0,len(headers)-1,width,normal)
        w.write_row(0,0,headers,head);w.set_row(0,42);w.freeze_panes(1,0)
        return w
    def formula(w,row,col,text,cache,fmt=num):
        w.write_formula(row,col,'='+text,fmt,'' if cache is None else cache)
    info=table('说明',['项目','采用内容'],25);info.set_column(1,1,105,wrap)
    details=[('方法','ΔCq=目标平均Cq−匹配内参平均Cq；ΔΔCq=ΔCq−校准组样本ΔCq均值；相对表达量=2^(-ΔΔCq)'),
             ('实际内参',json.dumps(model['reference'],ensure_ascii=False)),('实际校准组',json.dumps(model['calibrator'],ensure_ascii=False)),
             ('严格复孔阈值',.5),('辅助核对阈值',1.0),('生物学重复',str(model['params'].get('biological_replicates',False))),
             ('误差条',model['params'].get('error_bar','SD')+'；仅独立生物学 n≥2'),
             ('原始证据','; '.join(Path(p['path']).name+' | SHA256='+p['sha256'] for p in provenance)),('分析假设',json.dumps(model['assumptions'],ensure_ascii=False)),
             ('方法来源','Livak & Schmittgen, Methods 2001, DOI 10.1006/meth.2001.1262；QC阈值与默认内参为用户项目规则'),
             ('验证状态','独立复算与静态检查；真实引擎重算及渲染状态见同目录运行报告，未执行不能声称通过'),
             ('更新范围','原始Cq和Excluded可在既定映射下重算；身份、范围、纳入集合、复孔/图表结构变化须重跑分析并重新验收。'),
             ('适用性','未凭Cq表认证扩增曲线、熔解特异性、效率或内参稳定性。NTC/-RT控制证据不参与表达量。')]
    for r,(key,value) in enumerate(details,1):info.write(r,0,key,normal);info.write(r,1,value,wrap);info.set_row(r,36 if len(str(value))>65 else 24)
    # B5/B6 are shared, editable project threshold parameters.
    raw=table('原始数据',['源文件','源工作表','原始行','分析范围','运行','孔位','分组','样本','生物学重复','基因','Assay','类型','Cq原值','Excluded原值','排除解析','固定纳入限制','数值Cq（解析）','参与计数','有效Cq','复孔组ID','原始状态','完整原始行JSON'],16)
    raw.set_column(0,0,28);raw.set_column(15,15,30);raw.set_column(20,20,34)
    raw.set_column(6,6,28)
    q_for={idx:j for j,q in enumerate(model['qc']) for idx in q['indexes']}
    for i,r in enumerate(model['rows'],1):
        fixed=r.get('manual_reason','') or (r['reason'] if r.get('mapping_error') or '重复导出' in r['reason'] or '冲突' in r['reason'] or '缺少' in r['reason'] or '类型未知' in r['reason'] else '')
        values=[Path(r.get('file','')).name,r.get('sheet',''),r.get('source_row',''),r['scope'],r['run'],r['well'],r.get('group',''),r['sample'],r['bio_id'],r['gene'],r['assay'],r['kind'],r['cq_raw'],r['excluded_raw']]
        for j,value in enumerate(values):raw.write(i,j,'' if value is None else value,normal)
        raw.write(i,15,fixed,normal);raw.write(i,19,q_for[i-1],integer);raw.write(i,20,r['reason'],normal)
        raw.write(i,21,json.dumps({'source_file':r.get('file',''),'original':r.get('original',{})},ensure_ascii=False,default=str),normal)
        nr='N%d'%(i+1);mq='M%d'%(i+1)
        excluded='IF(OR('+nr+'=TRUE,LOWER('+nr+'&"")="true",'+nr+'="1",LOWER('+nr+'&"")="excluded",LOWER('+nr+'&"")="yes",'+nr+'="是"),1,IF(OR('+nr+'="",'+nr+'=FALSE,LOWER('+nr+'&"")="false",'+nr+'="0",LOWER('+nr+'&"")="no",'+nr+'="否",LOWER('+nr+'&"")="not excluded"),0,"状态不明"))'
        from core import exclude
        ex=exclude(r['excluded_raw'])
        formula(raw,i,14,excluded,1 if ex is True else 0 if ex is False else '状态不明',normal)
        formula(raw,i,16,'IF('+mq+'="","",IF(ISNUMBER('+mq+'),'+mq+',IFERROR(VALUE('+mq+'),"")))',float(r['value']) if r['value'] is not None else None)
        formula(raw,i,17,'IF(AND(ISNUMBER(Q{0}),O{0}=0,P{0}=""),1,0)'.format(i+1),1 if r['included'] else 0,integer)
        formula(raw,i,18,'IF(R{0}=1,Q{0},"")'.format(i+1),float(r['value']) if r['included'] else None)
    last=len(model['rows'])+1
    qc=table('复孔质控',['分析范围','分组','样本/生物学ID','Assay','基因','类型','全部孔位','各孔原始Cq','有效孔数','平均Cq','最大差值','严格QC','映射异常'],18)
    qc.set_column(6,7,32);qc.set_column(11,12,28)
    qc.set_column(1,1,28)
    for j,q in enumerate(model['qc'],1):
        scope,group,sample,assay,kind=q['key'];gene=q['gene']
        qc.write_row(j,0,[scope,group,sample,assay,gene,kind,' | '.join(model['rows'][i]['well'] for i in q['indexes'])],normal)
        joined='&" | "&'.join(ref('原始数据',12,i+1) for i in q['indexes'])
        formula(qc,j,7,joined or '""',' | '.join(str(model['rows'][i]['cq_raw']) for i in q['indexes']),normal)
        formula(qc,j,8,'COUNTIFS(\'原始数据\'!$T$2:$T${0},{1},\'原始数据\'!$R$2:$R${0},1)'.format(last,j-1),q['n'],integer)
        formula(qc,j,9,'IF(I{0}=0,"",SUMIFS(\'原始数据\'!$S$2:$S${1},\'原始数据\'!$T$2:$T${1},{2})/I{0})'.format(j+1,last,j-1),q['mean'])
        active=[ref('原始数据',18,i+1) for i in q['indexes']]
        formula(qc,j,10,'IF(I{0}<2,"",ROUND({1}-{2},{3}))'.format(j+1,aggregate('MAX',active),aggregate('MIN',active),q['precision']),q['spread'])
        formula(qc,j,11,'IF(I{0}=0,"无有效 Cq",IF(I{0}=1,"复孔不足",IF(K{0}<\'说明\'!$B$5,"严格合格",IF(K{0}<\'说明\'!$B$6,"未达到严格标准","严重不合格"))))'.format(j+1),q['state'],normal)
        qc.write(j,12,'; '.join(q['blocking']),normal)
    if model['qc']:
        qc.conditional_format(1,11,len(model['qc']),11,{'type':'cell','criteria':'==','value':'"严格合格"','format':green})
        qc.conditional_format(1,11,len(model['qc']),11,{'type':'cell','criteria':'==','value':'"未达到严格标准"','format':orange})
        qc.conditional_format(1,11,len(model['qc']),11,{'type':'cell','criteria':'==','value':'"严重不合格"','format':red})
    calc=table('计算过程',['分析范围','分组','生物学/组级ID','基因','目标Assay','内参Assay','目标复孔组','目标有效孔数','目标平均Cq','内参有效孔数','内参平均Cq','ΔCq','校准基准ΔCq','ΔΔCq','相对表达量','校准生物学/组级n','计算状态','QC来源状态','目标各孔Cq','内参各孔Cq','校准组'],18)
    calc.set_column(16,19,36)
    calc.set_column(1,1,28)
    for i,r in enumerate(model['results'],1):
        tq=model['qc'][r['target_qc']];rq=model['qc'][r['reference_qc']] if r['reference_qc'] is not None else None
        tr=r['target_qc']+1;rr=r['reference_qc']+1 if rq else None
        calc.write_row(i,0,[r['scope'],r['group'],r['sample'],r['gene'],r['assay'],r['reference'] or '',r['target_qc']],normal)
        for col,qrow,qcol,cache in [(7,tr,8,tq['n']),(8,tr,9,tq['mean']),(9,rr,8,rq['n'] if rq else None),(10,rr,9,rq['mean'] if rq else None),(18,tr,7,' | '.join(str(model['rows'][j]['cq_raw']) for j in tq['indexes'])),(19,rr,7,' | '.join(str(model['rows'][j]['cq_raw']) for j in rq['indexes']) if rq else None)]:
            formula(calc,i,col,ref('复孔质控',qcol,qrow) if qrow is not None else '""',cache,normal if col>=18 else num)
        valid_mapping=not tq['blocking'] and (rq is not None and not rq['blocking'])
        formula(calc,i,11,'IF(AND(ISNUMBER(I{0}),ISNUMBER(K{0}),{1}),I{0}-K{0},"")'.format(i+1,'TRUE' if valid_mapping else 'FALSE'),r['delta'])
        candidates=[j for j,x in enumerate(model['results']) if x['scope']==r['scope'] and x['assay']==r['assay'] and x['group']==r['calibrator']]
        drefs=[ref('计算过程',11,j+1) for j in candidates]
        count=aggregate('COUNT',drefs)
        formula(calc,i,15,count,len(r['calibration_rows']),integer)
        formula(calc,i,12,'IF(P{0}=0,"",{1})'.format(i+1,aggregate('AVERAGE',drefs)),r['baseline'])
        formula(calc,i,13,'IF(AND(ISNUMBER(L{0}),ISNUMBER(M{0})),L{0}-M{0},"")'.format(i+1),r['dd'])
        formula(calc,i,14,'IF(AND(ISNUMBER(N{0}),N{0}>-1024,N{0}<1074),2^(-N{0}),"")'.format(i+1),r['expression'])
        base=r['status'] if not valid_mapping or not r['reference'] or not r['calibrator'] else None
        status='"'+base.replace('"','""')+'"' if base else 'IF(NOT(ISNUMBER(I{0})),"无有效目标 Cq，无法计算",IF(NOT(ISNUMBER(K{0})),"缺少匹配内参，无法计算",IF(P{0}=0,"缺少可计算校准样本，无法计算",IF(ISNUMBER(O{0}),"可计算","表达量超出数值范围"))))'.format(i+1)
        formula(calc,i,16,status,r['status'],normal)
        risks=[]
        for label,qrow in [('目标',tr),('内参',rr)]:
            if qrow is not None:
                c=ref('复孔质控',11,qrow);risks.append('IF('+c+'="严格合格","","'+label+':"&'+c+'&"; ")')
        for j in candidates:
            for label,qi in [('校准目标',model['results'][j]['target_qc']),('校准内参',model['results'][j]['reference_qc'])]:
                if qi is not None:
                    c=ref('复孔质控',11,qi+1);risks.append('IF('+c+'="严格合格","","'+label+':"&'+c+'&"; ")')
        formula(calc,i,17,'&'.join(risks) if risks else '""','; '.join(r['qc']) or '',normal)
        calc.write(i,20,r['calibrator'] or '',normal)
    tidy=ws['整理数据'];tidy.hide_gridlines(2);tidy.set_column(0,1,25,normal);tidy.set_column(2,2,22,num)
    for i,r in enumerate(model['results']):
        for col,src,cache in [(0,1,r['group']),(1,3,r['gene']),(2,14,r['expression'])]:
            formula(tidy,i,col,ref('计算过程',src,i+1),cache,num if col==2 else normal)
    chartws=table('作图',['分析范围','基因','Assay','分组','实际n','平均表达量','SD/SEM','QC提示'],18)
    chartws.set_column(7,7,44);chartws.set_column(10,40,16)
    chartws.set_column(3,3,28)
    for i,s in enumerate(model['summaries'],1):
        chartws.write_row(i,0,[s['scope'],s['gene'],s['assay'],s['group']],normal)
        cells=[ref('计算过程',14,j+1) for j in s['rows']]
        formula(chartws,i,4,aggregate('COUNT',cells),s['n'],integer)
        formula(chartws,i,5,'IF(E{0}=0,"",{1})'.format(i+1,aggregate('AVERAGE',cells)),s['mean'])
        error=aggregate('STDEV',cells)
        if model['params'].get('error_bar','SD')=='SEM':error+=' /SQRT(E%d)'%(i+1)
        formula(chartws,i,6,'IF(E{0}<2,"",{1})'.format(i+1,error) if model['params'].get('biological_replicates') else '""',s['error'])
        qcells=[ref('计算过程',17,j+1) for j in s['rows']]
        formula(chartws,i,7,'&'.join(qcells) if qcells else '""','; '.join(s['qc']),normal)
    charts=defaultdict(list)
    for i,s in enumerate(model['summaries'],1):charts[(s['scope'],s['assay'],s['gene'])].append((i,s))
    palette=['#4F6D8A','#8B6F8E','#688C79','#A48263']
    chart_refs=[];cursor=max(len(model['summaries'])+4,6)
    for ci,((scope,assay,gene),entries) in enumerate(charts.items()):
        top=cursor;chartws.write(top,0,scope+' / '+assay,normal)
        chartws.write(top,7,'风险值保留；缺失不表示零。',normal)
        # Separate overlapping series give n=1 categories no error-bar object at all.
        data_top=top+1;cat_col=10
        chartws.write(data_top-1,cat_col,'分组',head)
        for k,(sr,s) in enumerate(entries):chartws.write(data_top+k,cat_col,s['group'],normal)
        chart=wb.add_chart({'type':'column'})
        for k,(sr,s) in enumerate(entries):
            val_col=cat_col+1+2*k;err_col=val_col+1
            chartws.write(data_top-1,val_col,s['group']+' mean',head)
            chartws.write(data_top-1,err_col,s['group']+' error',head)
            # Non-calculable categories remain physically blank in native plot ranges.
            if s['mean'] is None:continue
            formula(chartws,data_top+k,val_col,'F%d'%(sr+1),s['mean'])
            series={'categories':['作图',data_top,cat_col,data_top+len(entries)-1,cat_col],
                    'values':['作图',data_top,val_col,data_top+len(entries)-1,val_col],
                    'fill':{'color':palette[ci%len(palette)]},'border':{'none':True},'overlap':100,'gap':75}
            if s['error'] is not None:
                formula(chartws,data_top+k,err_col,'G%d'%(sr+1),s['error'])
                er='='+ref('作图',err_col,data_top)+':'+ref('作图',err_col,data_top+len(entries)-1).split('!')[1]
                series['y_error_bars']={'type':'custom','plus_values':er,'minus_values':er,'end_style':1,'line':{'color':'#334155','width':1}}
            chart.add_series(series)
        if not chart.series:
            chartws.write(top+2,0,'该目标无可计算表达量，不生成空图。',normal)
        else:
            chart.set_title({'none':True});chart.set_legend({'none':True})
            chart.set_x_axis({'label_position':'low','line':{'color':'#334155','width':1.25},'num_font':{'name':'Microsoft YaHei','size':10}})
            chart.set_y_axis({'min':0,'crossing':0,'name':gene+' relative expression','line':{'none':True},
                              'major_gridlines':{'visible':False},'name_font':{'name':'Arial','size':11}})
            chart.set_size({'width':680,'height':330});chart.set_chartarea({'border':{'none':True}})
            chart.show_blanks_as('gap');chartws.insert_chart(top+2,0,chart)
            chart_refs.append({'scope':scope,'assay':assay,'gene':gene,'anchor_row':top+3})
        cursor+=22
    # Formula summary and full anomaly list live in the required explanation sheet.
    base_row=len(details)+3
    qlast=len(model['qc'])+1
    sample_rows=[j+1 for j,q in enumerate(model['qc']) if q['key'][4]=='sample']
    states=[ref('复孔质控',11,j) for j in sample_rows]
    for offset,label,expr,cache in [
        (0,'复孔组总数',str(len(sample_rows)),len(sample_rows)),
        (1,'严格合格复孔组数','+'.join('IF('+c+'="严格合格",1,0)' for c in states) or '0',sum(model['qc'][j-1]['state']=='严格合格' for j in sample_rows)),
        (2,'非严格合格复孔组数','B{0}-B{1}'.format(base_row+1,base_row+2),sum(model['qc'][j-1]['state']!='严格合格' for j in sample_rows)),
        (3,'有效检测孔数','SUM(\'原始数据\'!R2:R%d)'%last,sum(r['included'] for r in model['rows'])),
        (4,'最大复孔差值',aggregate('MAX',[ref('复孔质控',10,j) for j in sample_rows]) if model['max_spread'] is not None else '""',model['max_spread'])]:
        row=base_row+offset;info.write(row,0,label,normal);formula(info,row,1,expr,cache)
    info.write(base_row+5,0,'最大差值全部并列位置',normal)
    locs=[]
    for j in sample_rows:
        c=ref('复孔质控',10,j)
        label=' / '.join(str(x) for x in model['qc'][j-1]['key'][:4]).replace('"','""')
        locs.append('IF(AND(ISNUMBER('+c+'),'+c+'=B'+str(base_row+5)+'),"'+label+'; ","")')
    formula(info,base_row+5,1,'&'.join(locs) if locs else '""',json.dumps(model['max_locations'],ensure_ascii=False),wrap)
    info.write(base_row+6,0,'复孔 QC 结论',normal)
    mapping_clear='AND('+','.join(ref('复孔质控',12,j)+'=""' for j in sample_rows)+')' if sample_rows else 'FALSE'
    formula(info,base_row+6,1,'IF(AND(B{0}>0,B{1}=0,{2}),"全部复孔严格合格","存在不合格、复孔不足、缺失或映射异常；逐项见复孔质控")'.format(base_row+1,base_row+3,mapping_clear), '全部复孔严格合格' if model['all_pass'] else '存在复孔异常',wrap)
    info.write(base_row+8,0,'所有异常与缺失（生成时）',head)
    for i,issue in enumerate(model['issues'],base_row+9):
        info.write(i,0,issue['type'],normal);info.write(i,1,json.dumps(json_ready(issue),ensure_ascii=False),wrap);info.set_row(i,48)
    for name,w in ws.items():
        w.set_landscape();w.set_paper(9);w.fit_to_pages(1,0);w.set_margins(.3,.3,.4,.4)
        if name!='整理数据':w.repeat_rows(0)
        if name=='作图':w.print_area(0,0,max(cursor,5),7)
    wb.close()
    return {'sheets':SHEETS,'charts':chart_refs,'formula_rows':len(model['results']),
            'cell_map':{'raw_cq':[ref('原始数据',12,i+1) for i in range(len(model['rows']))],
                        'expression':[ref('计算过程',14,i+1) for i in range(len(model['results']))]}}


def inspect(path):
    import openpyxl
    wb=openpyxl.load_workbook(path,data_only=False)
    values=openpyxl.load_workbook(path,data_only=True)
    issues=[];formulas=0
    if wb.sheetnames!=SHEETS:issues.append('工作表顺序/名称不符合约定')
    tidy=wb['整理数据']
    if tidy.max_column>3:issues.append('整理数据超过三列')
    if tidy['A1'].value=='分组':issues.append('整理数据出现表头')
    for ws in wb:
        for row in ws:
            for cell in row:
                if cell.data_type=='f':
                    formulas+=1
                    if '#REF!' in cell.value:issues.append(ws.title+'!'+cell.coordinate+' 引用错误')
                if values[ws.title][cell.coordinate].data_type=='e':
                    issues.append(ws.title+'!'+cell.coordinate+' '+str(values[ws.title][cell.coordinate].value))
    wb.close();values.close()
    ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if re.fullmatch(r'xl/charts/chart\d+\.xml',n)]
        for name in names:
            root=ET.fromstring(z.read(name))
            if root.find('.//c:barChart',ns) is None:issues.append(name+' 非原生柱形图')
            if root.find('.//c:legend',ns) is not None:issues.append(name+' 显示图例')
            mins=root.findall('.//c:valAx/c:scaling/c:min',ns)
            if not mins or mins[0].get('val')!='0':issues.append(name+' 纵轴非零起点')
    return {'status':'passed' if not issues else 'failed','issues':issues,'formula_count':formulas,'native_chart_count':len(names)}
