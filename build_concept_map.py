#!/usr/bin/env python3
"""构建概念板块映射 — 从东财API获取"""
import json, urllib.request, ssl, os, time
ssl._create_default_https_context = ssl._create_unverified_context

CONCEPT_MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "concept_map.json")

def fetch_concept_stocks():
    """从东财获取热门概念板块及其成分股"""
    # 热门概念列表
    hot_concepts = [
        'BK0891',  # 机器人
        'BK0800',  # 人工智能
        'BK0493',  # 半导体
        'BK0489',  # 新能源
        'BK0478',  # 光伏
        'BK0868',  # 储能
        'BK0596',  # 军工
        'BK0464',  # 5G
        'BK0459',  # 芯片
        'BK0727',  # 数字经济
        'BK0987',  # 低空经济
        'BK0984',  # 飞行汽车
        'BK0904',  # 液冷
        'BK0986',  # 算力
        'BK0734',  # 数据要素
        'BK0950',  # 鸿蒙
        'BK0968',  # 固态电池
        'BK0427',  # 锂电池
        'BK0480',  # 新能源汽车
        'BK0473',  # 智能制造
    ]
    
    concept_map = {}
    
    for bk_code in hot_concepts:
        try:
            url = f"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=200&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:{bk_code}&fields=f12,f14"
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            items = data.get('data',{}).get('diff',[])
            
            # Get concept name
            bk_name = ""
            if items:
                bk_name = items[0].get('f14','').replace('概念','').replace('板块','')
            
            for item in items:
                code = item.get('f12','')
                if code and code.startswith(('60','00')):
                    if code not in concept_map:
                        concept_map[code] = []
                    if bk_name not in concept_map[code]:
                        concept_map[code].append(bk_name)
            
            print(f'  {bk_name}: {len(items)}只')
            time.sleep(0.3)  # 避免限流
        except Exception as e:
            print(f'  {bk_code}: ❌ {str(e)[:40]}')
    
    # Save
    with open(CONCEPT_MAP_FILE, 'w') as f:
        json.dump(concept_map, f, ensure_ascii=False, indent=2)
    
    print(f'\n✅ 概念映射已保存: {len(concept_map)}只股票')
    return concept_map

if __name__ == '__main__':
    fetch_concept_stocks()
