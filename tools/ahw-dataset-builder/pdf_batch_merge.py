#!/usr/bin/env python3
"""يدمج كل الدفعات في metadata واحد نهائي."""
import pandas as pd
from pathlib import Path
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample-dir', required=True)
    args = ap.parse_args()

    sample_dir = Path(args.sample_dir)
    all_dfs = []
    for batch_dir in sorted(sample_dir.glob('batch_*')):
        csv = batch_dir / 'metadata.csv'
        if csv.exists():
            df = pd.read_csv(csv)
            df['batch'] = batch_dir.name
            all_dfs.append(df)
            print(f"  ✓ {batch_dir.name}: {len(df)} كلمة")

    if not all_dfs:
        print("❌ لا توجد دفعات")
        return

    merged = pd.concat(all_dfs, ignore_index=True)
    merged.to_csv(sample_dir / 'metadata_all.csv', index=False, encoding='utf-8-sig')
    merged.to_excel(sample_dir / 'metadata_all.xlsx', index=False, engine='openpyxl')
    print(f"\n✅ الإجمالي: {len(merged)} كلمة → metadata_all.csv")

if __name__ == '__main__':
    main()
