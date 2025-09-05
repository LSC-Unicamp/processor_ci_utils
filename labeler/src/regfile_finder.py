# Cocotb uses SimHandleBase objects to represent HDL objects (signals, modules, etc.).

# You can differentiate between:

# Signals: SimHandle instances with _type indicating direction (e.g. reg, wire, input, output)

# Submodules: also SimHandle instances, but of type module

import cocotb

import argparse
import json
import os
import subprocess
import logging

def explore_current_module(dut):
    submodules = []
    arrays = []

    for name in dir(dut):
        if name.startswith('_'):
            continue  # Skip Python/Cocotb internals
        if callable(getattr(dut, name)):
            continue  # Skip methods like get_definition_name()

        obj_handle = getattr(dut, name)
        try:
            obj_type = obj_handle._type # This is the cocotb type (wire, reg, array, etc)

            obj_path = obj_handle._path # cocotb path including the instantiated modules

        except AttributeError:
            continue  # Not a SimHandle

        if obj_type == 'GPI_MODULE':
            submodules.append(name)
        elif obj_type == 'GPI_ARRAY':
            arrays.append([obj_handle, obj_path])

    return arrays, submodules


def explore_hierarchy(module, regfile_candidates=[]):

    arrays, submodules = explore_current_module(module)

    if arrays:
        for a in arrays:
            print(f"  {a[1]} [{len(a[0])}][{len(a[0][1])}]") # https://github.com/rafaelcalcada/rvx does not have registers[0]. Read directly from 1
            if len(a[0]) >= 31 and len(a[0]) <= 32 and len(a[0][1]) == 32: # 31 or 32 registers, 32-bit width registers
                regfile_data = {
                    "regfile_path": a[1]
                }
                regfile_candidates.append(regfile_data)

    for m in submodules:
        submodule_instance = getattr(module, m)
        regfile_candidates = explore_hierarchy(submodule_instance, regfile_candidates)

    return regfile_candidates

@cocotb.test()
async def find_register_file(dut):

    print("""
            #########################################################
            #Looking for the register file path - regfile_finder.py #
            #########################################################
          """)
    
    regfile_candidates = explore_hierarchy(dut)

    print("- Register File Candidates Found:")
    for i, candidate in enumerate(regfile_candidates):
        print(f"  {i + 1}: {candidate['regfile_path']}")
    print("\n")

    output_dir = os.environ.get('OUTPUT_DIR', "default")
    processor_name = os.path.basename(output_dir)

    output_file = os.path.join(output_dir, f"{processor_name}_reg_file.json")

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
    
    existing_data[processor_name] = {
        "regfile_candidates": regfile_candidates
    }

    # Save the updated data back to the JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(existing_data, json_file, indent=4)
        print(f'Results saved to {output_file}')
    except OSError as e:
        logging.warning('Error writing to JSON file: %s', e)
    dut._log.info(f"Register file candidates saved to {output_file}")


# This script is intended to be run as a cocotb testbench.
# If called directly, it will open a subprocess and run the cocotb simulation
# The simulation will run only the 'async def find_register_file(dut)' function
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This regfile_finder testbench runs a cocotb simulation and parses the design hierarchy to find the register file.")
    parser.add_argument("--makefile", required=True, help="Specify the cocotb makefile path")
    parser.add_argument("--output", required=True, default="detected_reg_file.json", help="Specify the output file path. Must be an absolute path.")
    args = parser.parse_args()

    if not os.path.isabs(args.output):
        raise ValueError("The --output argument must be an absolute path.")

    
    # These commands:
    # copy this file to the makefile directory
    # run the simulation to find the register file
    # remove the copy
    # TODO: change this to use "PYTHONPATH" and "make -f"

    makefile_dir = os.path.dirname(os.path.abspath(args.makefile))
    subprocess.run(["cp", __file__, makefile_dir])

    module_name = os.path.splitext(os.path.basename(__file__))[0]
    subprocess.run(["make", f"MODULE={module_name}", f"OUTPUT_FILE={args.output}"], cwd=makefile_dir)

    file_copy_path = os.path.join(makefile_dir, os.path.basename(__file__))
    subprocess.run(["rm", "-f", file_copy_path], cwd=makefile_dir)


    
