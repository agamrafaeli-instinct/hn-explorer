#!/usr/bin/env python3
"""Incrementally maintain schema-v1 HN CSVs; no API failure advances checkpoint."""
import argparse, concurrent.futures, csv, datetime as dt, hashlib, io, json, os
import pathlib, shutil, sqlite3, tempfile, time, urllib.request
from prepare_data import NAMES, COLUMNS, normalize, encode
from concentration import compute as concentration
from terms import compute as terms
import redact_secrets, archive_append
API = 'https://hacker-news.firebaseio.com/v0'
DBCOLS = 'id,type,author,time,title,url,domain,score,comments,text,dead,deleted'


def fetch(path):
    for attempt in range(6):
        try:
            req = urllib.request.Request(API + '/' + path + '.json', headers={'User-Agent': 'hn-explorer-daily/1.0'})
            with urllib.request.urlopen(req, timeout=35) as r:
                return json.load(r)
        except Exception:
            if attempt == 5: raise
            time.sleep(min(2 ** attempt, 20))


def csv_row(row):
    return [int(v) if v != '' else None for v in row[:1]] + [
        int(v) if i in (3,7,8,10,11) and v != '' else (None if v == '' else v)
        for i,v in enumerate(row[1:],1)]


def summaries(db, stamp):
    totals = db.execute('SELECT count(*),coalesce(sum(score),0),coalesce(sum(comments),0),sum(dead),sum(deleted),sum(time IS NULL),sum(score IS NULL),sum(comments IS NULL) FROM items').fetchone()
    return {'schema_version':1,'generated_at':stamp,'total_rows':totals[0],
        'totals':dict(zip(['posts','score_sum','comments_sum','dead','deleted','missing_time','missing_score','missing_comments'],totals)),
        'time_range':dict(zip(['min','max'],db.execute('SELECT min(time),max(time) FROM items').fetchone())),
        'type_counts':dict(db.execute('SELECT type,count(*) FROM items GROUP BY type ORDER BY count(*) DESC,type')),
        'monthly':[dict(zip(['month','posts','score_sum','comments_sum'],r)) for r in db.execute("SELECT strftime('%Y-%m',time,'unixepoch'),count(*),coalesce(sum(score),0),coalesce(sum(comments),0) FROM items WHERE time IS NOT NULL GROUP BY 1 ORDER BY 1")],
        'top_domains':[dict(zip(['domain','posts'],r)) for r in db.execute("SELECT domain,count(*) FROM items WHERE domain IS NOT NULL AND domain<>'' GROUP BY domain ORDER BY count(*) DESC,domain LIMIT 100")],
        'top_authors':[dict(zip(['by','posts'],r)) for r in db.execute("SELECT author,count(*) FROM items WHERE author IS NOT NULL AND author<>'' GROUP BY author ORDER BY count(*) DESC,author LIMIT 100")],
        'top_posts':[{k:v for k,v in zip(NAMES,r) if k!='text'} for r in db.execute('SELECT '+DBCOLS+' FROM items ORDER BY score DESC,time DESC,id DESC LIMIT 100')],
        'concentration': concentration(db), 'terms': terms(db)}


# Rolling window size kept in data/posts-*.csv. One setting; the archive plan (docs/BACKFILL_PLAN.md) lifts the cap later.
RETENTION_ROWS = 1000000


def update(root, workers=32, limit=RETENTION_ROWS, getter=fetch, max_new=250000):
    redaction_start=redact_secrets.n
    root=pathlib.Path(root).resolve(); data=root/'data'
    manifest=json.loads((data/'manifest.json').read_text())
    if manifest['schema_version'] != 1 or [c['name'] for c in manifest['columns']] != NAMES:
        raise ValueError('Unsupported schema; refusing to update')
    checkpoint=manifest.get('daily_update',{}).get('last_scanned_id',max(c['max_id'] for c in manifest['chunks']))
    upper=getter('maxitem')
    if not isinstance(upper,int) or upper<checkpoint: raise ValueError('Invalid/regressed source maxitem')
    if upper-checkpoint>max_new: raise ValueError('Catch-up exceeds safety bound; rerun manually with a higher --max-new')
    retry=manifest.get('daily_update',{}).get('unavailable_ids',[])
    ids=sorted(set(range(checkpoint+1,upper+1)) | set(retry))
    if not ids:
        print('No new IDs; dataset unchanged'); return False
    # Stage inside the repo: os.replace below must stay on one filesystem, and /tmp can be a
    # different device on the runner (Errno 18, 2026-10-20).
    with tempfile.TemporaryDirectory(prefix='hn-daily-', dir=root) as tmp:
        tmp=pathlib.Path(tmp); db=sqlite3.connect(tmp/'items.db')
        db.execute('PRAGMA journal_mode=OFF'); db.execute('PRAGMA synchronous=OFF')
        db.execute('CREATE TABLE items (id INTEGER PRIMARY KEY,type TEXT,author TEXT,time INTEGER,title TEXT,url TEXT,domain TEXT,score INTEGER,comments INTEGER,text TEXT,dead INTEGER,deleted INTEGER,origin TEXT)')
        origins={c['path']:c for c in manifest['chunks']}
        previous=None; loaded=0
        for c in manifest['chunks']:
            p=(root/c['path']).resolve()
            if p.parent!=data: raise ValueError('Unsafe chunk path')
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            if digest!=c['sha256'] or p.stat().st_size!=c['bytes']: raise ValueError('Chunk integrity mismatch: '+c['path'])
            count=0
            with p.open(newline='',encoding='utf-8') as f:
                reader=csv.reader(f)
                if next(reader)!=NAMES: raise ValueError('Unexpected CSV header')
                for values in reader:
                    if len(values)!=len(NAMES): raise ValueError('Invalid CSV row')
                    row=csv_row(values); key=(row[3] is not None,row[3] or 0,row[0])
                    if previous is not None and key>previous: raise ValueError('Existing dataset not newest-first')
                    previous=key
                    db.execute('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',row+[c['path']]); count+=1
            if count!=c['rows']: raise ValueError('Chunk row-count mismatch')
            loaded+=count; db.commit()
        if loaded!=manifest['total_rows']: raise ValueError('Manifest row-count mismatch')
        unavailable=[]; added=0
        def get_item(i): return i,getter('item/'+str(i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for i,raw in pool.map(get_item,ids):
                if raw is None:
                    unavailable.append(i); continue
                if raw.get('id')!=i: raise ValueError('Source returned a different item ID')
                row=normalize(redact_secrets.redact_item(raw))
                cursor=db.execute('INSERT OR IGNORE INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',row+[None])
                added+=cursor.rowcount
        db.commit()
        # This is a rolling newest-by-creation-time window, not an archive.
        # Stories that leave the window are kept in data/archive (slice 6). Staged here, moved in below.
        leaving=db.execute("SELECT id,time,title,url,score,comments FROM items WHERE type='story' AND time IS NOT NULL AND id NOT IN (SELECT id FROM items ORDER BY time DESC,id DESC LIMIT ?)",(limit,)).fetchall()
        arch_staged=tmp/'archive_staged'; arch_names=archive_append.stage(root,leaving,arch_staged)
        db.execute('DELETE FROM items WHERE id NOT IN (SELECT id FROM items ORDER BY time DESC,id DESC LIMIT ?)',(limit,)); db.commit()
        kept=dict(db.execute('SELECT origin,count(*) FROM items WHERE origin IS NOT NULL GROUP BY origin'))
        staged=tmp/'staged'; staged.mkdir(); chunks=[]; header=encode(NAMES)
        buffer=bytearray(header); buffered=[]
        def flush():
            nonlocal buffer,buffered
            if not buffered: return
            sha=hashlib.sha256(buffer).hexdigest(); name='posts-inc-'+sha[:24]+'.csv'
            (staged/name).write_bytes(buffer)
            stamps=[r[3] for r in buffered if r[3] is not None]
            chunks.append({'path':'data/'+name,'rows':len(buffered),'bytes':len(buffer),'sha256':sha,
                           'min_id':min(r[0] for r in buffered),'max_id':max(r[0] for r in buffered),
                           'min_time':min(stamps) if stamps else None,'max_time':max(stamps) if stamps else None})
            buffer=bytearray(header); buffered=[]
        target=manifest['chunk_target_bytes']
        # Preserve a chunk only when its entire retained run stays contiguous.
        current=None; run=[]
        def output_run(origin,rows):
            if origin is not None and len(rows)==origins[origin]['rows'] and kept.get(origin)==len(rows):
                flush(); chunks.append(origins[origin]); return
            for row in rows:
                payload=encode(row)
                if len(header)+len(payload)>target: raise ValueError('Oversized row; no truncation')
                if len(buffer)+len(payload)>target: flush()
                buffer.extend(payload); buffered.append(row)
        for row in db.execute('SELECT '+DBCOLS+',origin FROM items ORDER BY time DESC,id DESC'):
            origin=row[-1]
            if run and origin!=current:
                output_run(current,run); run=[]
            current=origin; run.append(row[:-1])
        if run: output_run(current,run)
        flush()
        stamp=dt.datetime.now(dt.timezone.utc).isoformat(); summary=summaries(db,stamp)
        if not summary['total_rows']: raise ValueError('Would produce an empty dataset')
        new=dict(manifest); new.update(generated_at=stamp,total_rows=summary['total_rows'],chunks=chunks,total_csv_bytes=sum(c['bytes'] for c in chunks))
        new['daily_update']={'last_scanned_id':upper,'previous_scanned_id':checkpoint,'unavailable_ids':unavailable,
            'new_rows':added,'archived_stories':len(leaving),'retention_rows':limit,'mode':'daily additions since last successful scan; catch-up included',
            'score_policy':'snapshot at first retrieval; older scores/comments are not refreshed',
            'redaction_policy':'credential-shaped strings in text/title/url replaced using scripts/redact_secrets.py',
            'redacted_strings_this_run':redact_secrets.n-redaction_start}
        new['source']=dict(manifest.get('source',{})); new['source']['daily_update_api']=API
        new['source']['selection_after_daily_update']='latest retained items by time DESC, id DESC; all item types; unavailable IDs retried'
        for name,obj in [('manifest.json',new),('summary.json',summary)]:
            (staged/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        keep={c['path'] for c in chunks}
        site_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts and 'data'!=p.relative_to(root).parts[0])
        proposed=site_bytes+new['total_csv_bytes']+(staged/'manifest.json').stat().st_size+(staged/'summary.json').stat().st_size
        if proposed>900000000: raise ValueError('Site exceeds 900 MB safety budget; dataset left unchanged')
        # Archive first: a rerun skips ids already archived, so a failure after this point loses nothing.
        for n in arch_names: os.replace(arch_staged/n,data/'archive'/n)
        for p in staged.iterdir(): os.replace(p,data/p.name)
        for c in manifest['chunks']:
            if c['path'] not in keep: (root/c['path']).unlink()
        print(json.dumps({'new_rows':added,'total_rows':new['total_rows'],'last_scanned_id':upper,'unavailable_ids':len(unavailable),'site_bytes':proposed,'preserved_chunks':sum(c['path'] in origins for c in chunks)}))
    return True


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',default='.'); p.add_argument('--workers',type=int,default=32)
    p.add_argument('--retention-rows',type=int,default=RETENTION_ROWS); p.add_argument('--max-new',type=int,default=250000)
    a=p.parse_args()
    if not 1<=a.workers<=64 or a.retention_rows<1: p.error('Invalid worker count or retention')
    update(a.root,a.workers,a.retention_rows,max_new=a.max_new)
