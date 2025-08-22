import cocotb
import re
import os
import json
import logging
from word_size import count_bits
from regfile_finder import find_register_file
from cycle import instr_mem_driver, test_pc_behavior
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock

def resolve_path(dut, path: str):
    """Resolve a string path like 'processorci_top.u_core.regs[5]' into a cocotb handle."""
    parts = path.split('.')
    # Drop the first part if it matches top-level name
    if parts[0] == dut._name:
        parts = parts[1:]

    handle = dut
    for part in parts:
        if '[' in part and ']' in part:
            # Array element, e.g. regs[5]
            name, idx = part[:-1].split('[')
            handle = getattr(handle, name)[int(idx)]
        else:
            handle = getattr(handle, part)
    return handle



@cocotb.test()
async def processor_test(dut):
    """Test function for the processor.

    Args:
        dut: The design under test.
    """

    bits = count_bits(dut, None)

    find_register_file(dut)

    output_dir = os.environ.get('OUTPUT_DIR', "default")
    processor_name = os.path.basename(output_dir)
    print(f"Processor name: {output_dir}")

    # Load register file candidates
    regfile_candidates = []
    try:
        with open(os.path.join(output_dir, f"{processor_name}_reg_file.json"), 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            regfile_candidates = data.get(processor_name, {}).get("regfile_candidates", [])
    except (json.JSONDecodeError, OSError) as e:
        logging.warning('Error reading register file candidates: %s', e)
    if not regfile_candidates:
        dut._log.error("No register file candidates found. Please run regfile_finder.py first.")
        return
    dut._log.info(f"Register file candidates: {regfile_candidates}")    

    regfile_path = regfile_candidates[0]['regfile_path']
    print(f"Using register file: {regfile_path}")

    regfile = resolve_path(dut, regfile_path)
    print(f"Resolved register file: {regfile}")

    await test_pc_behavior(dut, regfile)

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
