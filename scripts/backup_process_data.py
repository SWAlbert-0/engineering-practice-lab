"""Consistent SQLite backup for D01/D09/D11/D13. Stop the service before restoring a backup."""
import argparse,os,sqlite3
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--project',choices=('process','requirements','repair','literature'),default='process');a=p.parse_args()
source=Path(os.environ.get('LAB_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data')))/(a.project+'.sqlite3')
target=Path(a.output).resolve()
if not source.exists():p.error('Database does not exist; start the service first.')
if target.exists() or target==source.resolve():p.error('Output must be a new file, separate from the live database.')
target.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:
    src.backup(dst)
    if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Backup integrity check failed')
print(a.project+' backup saved:',target)
