"""Explicit, loss-aware bridge from the recovered 21-field research protocol."""
import csv
import io

ADAPTER_VERSION = '0.1.1'
UNCERTAIN = {'unknown', 'unclear', 'not_applicable'}
FIELDS = ['match_id', 'game_number', 'point_number', 'server', 'receiver', 'server_score_before', 'receiver_score_before', 'serve_side', 'serve_length', 'serve_location', 'serve_spin', 'receive_type', 'receive_location', 'third_ball_attack', 'third_ball_side', 'third_ball_outcome', 'rally_length', 'point_winner', 'point_outcome', 'video_timestamp', 'notes']
CORE = {'match_id','game_number','point_number','server','receiver','server_score_before','receiver_score_before','point_winner'}
CATEGORIES = {
    'server': {'player','opponent'}, 'receiver': {'player','opponent'},
    'point_winner': {'player','opponent'}, 'point_outcome': {'win','loss'},
    'serve_side': {'forehand','backhand'}, 'serve_length': {'short','half_long','long'},
    'serve_location': {'forehand','middle','backhand'},
    'serve_spin': {'backspin','sidespin','topspin','no_spin','mixed'},
    'receive_type': {'push','flick','chiquita','drive','loop','long_push','short_touch','other'},
    'receive_location': {'forehand','middle','backhand'},
    'third_ball_attack': {'yes','no'}, 'third_ball_side': {'forehand','backhand','other'},
    'third_ball_outcome': {'successful','unsuccessful'},
}

def convert(original):
    from core.engine import ingest
    issues=[]; converted=[]
    def notice(level,row,field,message): issues.append(dict(level=level,row=row,field=field,message=message))
    match_ids={r.get('match_id') for r in original}
    if len(match_ids)>1: notice('error',None,'match_id','一个文件只能导入一场比赛；请按 match_id 分开。')
    for n,r in enumerate(original,2):
        for field in CORE:
            if not r.get(field): notice('error',n,field,'历史协议必需的比赛状态字段缺失。')
        for field,allowed in CATEGORIES.items():
            value=r.get(field,'')
            if value and value not in allowed|UNCERTAIN: notice('error',n,field,'历史协议包含未定义类别：'+value)
        for field in ['game_number','point_number','server_score_before','receiver_score_before','rally_length']:
            value=r.get(field,'')
            if value and value not in UNCERTAIN:
                try:
                    if int(value)<(1 if field in {'game_number','point_number','rally_length'} else 0): raise ValueError()
                except ValueError: notice('error',n,field,'需要有效整数或明确的不确定性标签。')
        s={'player':'A','opponent':'B'}.get(r.get('server')); winner={'player':'A','opponent':'B'}.get(r.get('point_winner'))
        receiver={'player':'A','opponent':'B'}.get(r.get('receiver'))
        if not s or not winner or not receiver or s==receiver:
            notice('error',n,'server/receiver/point_winner','身份未知或冲突，无法可靠映射 A/B；不根据比分推测身份。');continue
        try: before={s:int(r['server_score_before']),receiver:int(r['receiver_score_before'])}
        except (KeyError,ValueError):
            notice('error',n,'score_before','比分未知，无法生成可靠的赛后比分；不补猜。');continue
        expected={'player':'win','opponent':'loss'}[r['point_winner']]
        if r.get('point_outcome') and r['point_outcome'] not in UNCERTAIN and r['point_outcome']!=expected:
            notice('error',n,'point_outcome','player 视角 win/loss 与 point_winner 冲突。')
        before[winner]+=1
        row=dict(game=r.get('game_number',''),point=r.get('point_number',''),server=s,winner=winner,score_a=str(before['A']),score_b=str(before['B']),rally_length=r.get('rally_length',''),third_ball_attack=r.get('third_ball_attack',''),serve_type=r.get('serve_spin',''),receive_type=r.get('receive_type',''),point_phase='',outcome='',serve_placement='')
        length,location=r.get('serve_length',''),r.get('serve_location','')
        if length in {'short','long'} and location in {'forehand','backhand','middle'}:
            row['serve_placement']=length+'_'+{'forehand':'fh','backhand':'bh','middle':'middle'}[location]
        elif length in UNCERTAIN or location in UNCERTAIN:
            row['serve_placement']=next((x for x in ['not_applicable','unknown','unclear'] if x in {length,location}),'')
        elif length or location: notice('warning',n,'serve_placement','half_long 或不完整落点无法无损转换成产品六区；原始字段已保留。')
        receive_map={'chiquita':'flick','drive':'attack','loop':'attack','long_push':'push','short_touch':'push'}
        if row['receive_type'] in receive_map:
            notice('warning',n,'receive_type',f'接发类别 {row["receive_type"]} 合并为 {receive_map[row["receive_type"]]}；细分类别保留在 source_receive_type。')
            row['receive_type']=receive_map[row['receive_type']]
        row.update({'source_'+k:v for k,v in r.items() if k is not None})
        converted.append(row)
    for field in FIELDS:
        if original and field not in original[0]: notice('warning',None,field,'历史 CSV 未提供此字段；不会补猜。')
    notice('warning',None,'perspective','固定映射：player=A，opponent=B。请将导入页面的 A/B 姓名按此填写。')
    notice('warning',None,'point_outcome/third_ball_outcome','win/loss 不等于 winner/error；第三板即时结果不等于该分最终获胜。这些原始值保留，不转换为产品 outcome。')
    if any(i['level']=='error' for i in issues):
        return converted,dict(valid=False,issues=issues,row_count=len(original))
    if not converted: return [],dict(valid=False,issues=[dict(level='error',row=1,field='csv',message='历史 CSV 没有比赛数据。')],row_count=0)
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=converted[0].keys());writer.writeheader();writer.writerows(converted)
    rows,validation=ingest(stream.getvalue().encode('utf-8'),allow_uncertainty=True)
    validation['issues']=issues+validation['issues']
    return rows,validation
