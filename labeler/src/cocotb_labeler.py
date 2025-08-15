import cocotb
import re
import os
import json
import logging
from word_size import count_bits
from cycle import instr_mem_driver, test_pc_behavior
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock

@cocotb.test()
async def processor_test(dut):
    """Test function for the processor.

    Args:
        dut: The design under test.
    """

    bits = count_bits(dut, None)

    test_pc_behavior(dut)

    output_dir = os.environ.get('OUTPUT_DIR', "default")
    processor_name = os.path.basename(output_dir)
    print(f"Processor name: {output_dir}")

    output_file = os.path.join(output_dir, f"{processor_name}_labels.json")

    if not os.path.exists(output_file):
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump({}, json_file, indent=4)

    # Load existing JSON data
    try:
        with open(output_file, 'r', encoding='utf-8') as json_file:
            existing_data = json.load(json_file)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning('Error reading existing JSON file: %s', e)
        existing_data = {}

    existing_data[processor_name]["bits"] = bits

    # Save the updated data back to the JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(existing_data, json_file, indent=4)
        print(f'Results saved to {output_file}')
    except OSError as e:
        logging.warning('Error writing to JSON file: %s', e)
