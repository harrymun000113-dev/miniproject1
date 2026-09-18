"""A→B 실행 진입점. 프로젝트 역할별 모듈을 대체하지 않는다."""
import argparse
import json
from pathlib import Path

import pandas as pd
from src.collect_data_A import fetch_trade_data
from src.preprocess_kpi_B import preprocess_kpi_b


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='UN Comtrade 수집 및 Pandas KPI 전처리')
    parser.add_argument('--query', required=True, help='hs_code,year,country_code 열이 있는 CSV')
    parser.add_argument('--exchange-rate', type=float, default=None, help='확인된 USD/KRW 환율')
    parser.add_argument('--full-country-coverage', action='store_true', help='전체 비교국 목록 검증 완료 시에만 사용')
    parser.add_argument('--output-dir', default='data/processed')
    args = parser.parse_args()
    query_df = pd.read_csv(args.query, dtype={'hs_code': 'string', 'country_code': 'string'})
    raw_df = fetch_trade_data(query_df)
    processed_df = preprocess_kpi_b(raw_df, exchange_rate=args.exchange_rate,
                                    full_country_coverage=args.full_country_coverage)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_df.to_csv(output_dir / 'trade_raw.csv', index=False, encoding='utf-8-sig')
    processed_df.to_csv(output_dir / 'trade_processed.csv', index=False, encoding='utf-8-sig')
    (output_dir / 'quality_report.json').write_text(json.dumps({
        'collection': raw_df.attrs['collection_report'],
        'preprocessing': processed_df.attrs['quality_report'],
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'저장 완료: {output_dir.resolve()}')
