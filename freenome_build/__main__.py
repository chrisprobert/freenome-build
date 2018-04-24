from freenome_build.freenome_build import main as freenome_build_main
from freenome_build.freenome_build import parse_args

def main():
    args = parse_args()
    freenome_build_main(args)


if __name__ == "__main__":
    main()
