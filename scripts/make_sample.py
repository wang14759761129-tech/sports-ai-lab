"""Generate explicitly synthetic, reproducible legal point sequences."""
import csv
from pathlib import Path
import random
random.seed(14)
path=Path(__file__).resolve().parents[1]/'data/samples/synthetic.csv'
path.parent.mkdir(parents=True,exist_ok=True)
with path.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['game','point','server','winner','score_a','score_b','rally_length','third_ball_attack','serve_placement','serve_type','receive_type','point_phase','outcome']);w.writeheader()
    for game in range(1,4):
        a=b=0;p=0
        while max(a,b)<11 or abs(a-b)<2:
            t=a+b; switch=(t//2)%2 if t<20 else (10+t-20)%2
            server=('A' if game%2 else 'B') if not switch else ('B' if game%2 else 'A')
            winner='A' if random.random()<.57 else 'B';a+=winner=='A';b+=winner=='B';p+=1
            w.writerow(dict(game=game,point=p,server=server,winner=winner,score_a=a,score_b=b,rally_length=random.randint(1,14),third_ball_attack=random.choice(['yes','no']),serve_placement=random.choice(['short_bh','long_fh','short_middle']),serve_type=random.choice(['backspin','sidespin','no_spin']),receive_type=random.choice(['push','flick','attack']),point_phase=random.choice(['serve','receive','third_ball','rally']),outcome=random.choice(['winner','error'])))
