#!/usr/bin/env python3
"""Build the unified static site; validate in staging before replacing outputs."""
import argparse
import importlib.util
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from scanner.marketplaces import build as marketplaces
from scanner.marketplaces.render import nav

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('shopify_stats',ROOT/'1.Stats.py')
shopify=importlib.util.module_from_spec(spec)
spec.loader.exec_module(shopify)


def build(root=ROOT,as_of=None,refresh=False):
    root=Path(root).resolve();as_of=as_of or date.today()
    with tempfile.TemporaryDirectory(prefix='opportunity-build-') as directory:
        stage=Path(directory)
        shutil.copytree(root/'Data',stage/'Data')
        shutil.copytree(root/'HTML/assets',stage/'HTML/assets')
        shopify.build(stage,as_of)
        old=(stage/'HTML/index.html').read_text(encoding='utf-8')
        old=re.sub(r'<nav aria-label="Navigation">.*?</nav>',nav('shopify'),old,count=1)
        old=old.replace('href="#"><span class="brand-mark"','href="index.html"><span class="brand-mark"',1)
        (stage/'HTML/shopify.html').write_text(old,encoding='utf-8')
        result=marketplaces.build(stage,as_of,refresh)
        # Reject any broken internal static link before publishing the staged artifact.
        verify_links(stage/'HTML')
        outputs=[stage/'HTML',stage/'Data/Stats',stage/'Data/Analysis',stage/'Data/Marketplaces']
        for directory in outputs:
            for path in sorted(directory.rglob('*')):
                if path.is_file():
                    dest=root/path.relative_to(stage)
                    content=path.read_bytes()
                    if dest.exists() and dest.read_bytes()==content:
                        continue
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    temp=dest.with_name(dest.name+'.tmp')
                    temp.write_bytes(content);temp.replace(dest)
    return result


def verify_links(root):
    from html.parser import HTMLParser
    from urllib.parse import unquote,urlsplit
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            for name,value in attrs:
                if name in ('src','href') and value:self.paths.append(value)
    for path in root.rglob('*.html'):
        parser=Links();parser.feed(path.read_text(encoding='utf-8'))
        for href in parser.paths:
            parsed=urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target=(path.parent/unquote(parsed.path)).resolve()
            if not target.is_relative_to(root.resolve()) or not target.exists():
                raise ValueError(f'Broken local link in {path.name}: {href}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--as-of',type=date.fromisoformat,default=date.today())
    parser.add_argument('--refresh',action='store_true',help='Refresh bounded public JSON adapters before building')
    args=parser.parse_args()
    try:
        result=build(args.root,args.as_of,args.refresh)
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(f'Build failed; previous published artifact is unaffected: {error}',file=sys.stderr)
        return 1
    print(f'Built {len(result["marketplaces"])} marketplaces + Shopify; {result["snapshot_count"]} source snapshots. HTML/index.html')
    return 0


if __name__=='__main__':sys.exit(main())
