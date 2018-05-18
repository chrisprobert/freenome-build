import sys
import logging

logging.basicConfig(
    stream=sys.stderr, format='%(levelname)s\t%(asctime)-15s\t%(message)s', level=logging.DEBUG
)
