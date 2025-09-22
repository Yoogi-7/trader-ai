
import argparse, time
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=4)
    args = p.parse_args()
    print(f"Backfill job started for {args.years}y (stub).")
    time.sleep(1)
    print("Backfill done.")
if __name__ == "__main__":
    main()
