import os
import logging
from collections import Counter

def is_python_hdl(filepath: str) -> str | None:
    """Detect if a Python file uses an HDL library (Amaranth, MyHDL, Cocotb)."""
    hdl_signatures = {
        'Amaranth': ['from amaranth', 'import amaranth', 'Elaboratable'],
        'MyHDL':    ['from myhdl', 'import myhdl', '@block', '@always', 'Signal(']
    }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        for lang, keywords in hdl_signatures.items():
            if any(keyword in content for keyword in keywords):
                return lang
    except Exception:
        pass

    return None


def count_file_loc(filepath: str) -> int:
    """Count the non-empty, non-comment lines of code in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
    except Exception:
        return 0


def identify_language(directory: str) -> str:
    """Identify the main HDL language in a directory based on LOC,
    including Python-based HDLs and skipping irrelevant folders.

    Args:
        directory (str): The directory to search.

    Returns:
        str: The main HDL language by LOC.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s: %(message)s',
    )

    if not os.path.isdir(directory):
        logging.warning('Provided path is not a directory: %s', directory)
        return 'Unknown'

    file_extensions = {
        '.v':      'Verilog',
        '.sv':     'SystemVerilog',
        '.vhd':    'VHDL',
        '.vhdl':   'VHDL',
        '.scala':  'Scala (Chisel)',
        '.bs':     'Bluespec',
        '.bsv':    'Bluespec',
        '.spinal': 'SpinalHDL',
        '.fir':    'FIRRTL',
        '.mlir':   'MLIR',
    }

    ignored_dirs = {
        'test', 'tests', 'testbench', 'testbenches',
        'bench', 'benches', 'sim', 'simulation',
        'doc', 'docs', 'examples', 'ref', 'reference'
    }

    lang_loc_counter = Counter()
    total_loc = 0

    for root, _, files in os.walk(directory):
        path_parts = set(os.path.normpath(root).split(os.sep))
        if path_parts & ignored_dirs:
            continue

        for file in files:
            filepath = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            ext = ext.lower()

            language = file_extensions.get(ext)
            if ext == '.py':
                language = is_python_hdl(filepath)

            if language:
                loc = count_file_loc(filepath)
                lang_loc_counter[language] += loc
                total_loc += loc

    if not lang_loc_counter:
        return 'Unknown'

    for lang, loc in sorted(lang_loc_counter.items(), key=lambda x: -x[1]):
        percentage = (loc / total_loc) * 100 if total_loc else 0
        logging.info(f"{lang}: {loc} LOC ({percentage:.2f}%)")

    return lang_loc_counter.most_common(1)[0][0]
