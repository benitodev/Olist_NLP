import argparse
import time

from src.etl.build_context_recommendations import run as run_context_recommendations
from src.etl.build_item_item_cooccurrence import run as run_item_item_cooc
from src.etl.load_interactions import run as run_load_interactions
from src.etl.load_items import run as run_load_items


def run_all(include_raw_load: bool = False, write_recommendations: bool = True):
    start = time.time()

    print("=" * 60)
    print("Starting ETL pipeline...")
    print(f"include_raw_load       = {include_raw_load}")
    print(f"write_recommendations  = {write_recommendations}")
    print("=" * 60)

    if include_raw_load:
        from src.etl.load_data import run as run_load_data

        print("\n[1/5] Loading raw CSV tables into Postgres...")
        run_load_data()
    else:
        print("\n[skip] load_data skipped (raw staging not requested).")

    print("\n[2/5] Building items catalog...")
    run_load_items()

    print("\n[3/5] Building interactions table...")
    run_load_interactions()

    print("\n[4/5] Building item-item co-occurrence recommendations...")
    out_item_item = run_item_item_cooc(write=write_recommendations)

    print("\n[5/5] Building context recommendations...")
    run_context_recommendations()

    elapsed = time.time() - start

    print("\n" + "=" * 60)
    print("ETL pipeline finished successfully.")
    print(f"Elapsed time: {elapsed:.2f} seconds")

    if out_item_item is not None:
        print(f"Model name: {out_item_item['model_name']}")
        print(f"Coverage: {out_item_item['neighbors_meta']['coverage']:.4f}")
        print(f"Same-category@10: {out_item_item['same_cat_rate_top10']:.4f}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run full Olist ETL / recommendation pipeline."
    )
    parser.add_argument(
        "--with-raw-load",
        action="store_true",
        help="Also load raw CSV tables into Postgres before building derived tables.",
    )
    parser.add_argument(
        "--dry-run-recs",
        action="store_true",
        help="Compute item-item recommendations without writing them to Postgres.",
    )

    args = parser.parse_args()

    run_all(
        include_raw_load=args.with_raw_load,
        write_recommendations=not args.dry_run_recs,
    )


if __name__ == "__main__":
    main()
