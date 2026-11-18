import argparse
import json
import urllib.request
from .config import RAW, CODEBOOK, SOURCES


def main():
    parser = argparse.ArgumentParser(description="HomePulse development pipeline")
    parser.add_argument("command", choices=["download", "prepare", "train", "train-practical", "train-profile12"])
    args = parser.parse_args()
    if args.command == "download":
        RAW.parent.mkdir(parents=True, exist_ok=True)
        for key, path in [("csv", RAW), ("codebook", CODEBOOK)]:
            if not path.exists():
                urllib.request.urlretrieve(SOURCES[key], path)
            print(path)
    elif args.command == "prepare":
        from .data import prepare
        print(json.dumps(prepare(), indent=2))
    elif args.command == "train-profile12":
        from .home_profile_training import train
        train()
    elif args.command == "train-practical":
        from .practical_training import train_practical
        train_practical()
    else:
        from .training import train
        print(json.dumps(train(), indent=2))


if __name__ == "__main__":
    main()
