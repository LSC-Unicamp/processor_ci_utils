import os
import logging
import argparse
import sys
import re

from config import load_config

def escape_spaces(path: str) -> str:
    return re.sub(r'(?<!\\) ', r'\\ ', path)

def standard_makefile(processor_name: str, language: str, config_folder: str, output_dir: str, makefile_path: str, cocotb_name: str = 'cocotb_labeler'):

    config = load_config(config_folder, processor_name)

    # Load the processor configuration
    inc_dir = config['include_dirs']
    sim_files = config['files']
    if top_module == '':
        top_module = config['top_module']
    language_version = config['language_version']

    # Write the Makefile content
    with open(makefile_path, 'a', encoding='utf-8') as makefile:
        if language == 'verilog':
            makefile.write('SIM ?= icarus\n')
            makefile.write('TOPLEVEL_LANG ?= verilog\n')
            makefile.write(f'COMPILE_ARGS ?= -g{language_version}\n')
            for dirs in inc_dir:
                path = escape_spaces(f'cores/{processor_name}/{dirs}')
                makefile.write(f'VERILOG_INCLUDE_DIRS += {path}\n')
            for file in sim_files:
                path = escape_spaces(f'cores/{processor_name}/{file}')
                makefile.write(f'VERILOG_SOURCES += {path}\n')

        elif language == 'systemverilog':
            makefile.write('SIM ?= verilator\n')
            makefile.write('TOPLEVEL_LANG ?= verilog\n')
            makefile.write(f'COMPILE_ARGS ?= --language 1800-{language_version}\n')
            for dirs in inc_dir:
                path = escape_spaces(f'cores/{processor_name}/{dirs}')
                makefile.write(f'VERILOG_INCLUDE_DIRS += {path}\n')
            for file in sim_files:
                path = escape_spaces(f'cores/{processor_name}/{file}')
                makefile.write(f'VERILOG_SOURCES += {path}\n')

        elif language == 'vhdl':
            makefile.write('SIM ?= ghdl\n')
            makefile.write('TOPLEVEL_LANG ?= vhdl\n')
            makefile.write(f'COMPILE_ARGS ?= --std={language_version}\n')
            for dirs in inc_dir:
                path = escape_spaces(f'cores/{processor_name}/{dirs}')
                makefile.write(f'VHDL_INCLUDE_DIRS += {path}\n')
            for file in sim_files:
                path = escape_spaces(f'cores/{processor_name}/{file}')
                makefile.write(f'VHDL_SOURCES += {path}\n')

        makefile.write(f'TOPLEVEL = {top_module}\n')
        makefile.write(f'MODULE = {cocotb_name}\n')
        makefile.write(f'OUTPUT_DIR = {output_dir}/{processor_name}\n')
        makefile.write('export OUTPUT_DIR\n')
        makefile.write('include $(shell cocotb-config --makefiles)/Makefile.sim\n')

    return makefile_path



def processor_top_makefile(processor_name: str, config_folder: str, top_folder: str, output_dir: str, makefile_path: str, cocotb_name: str = 'cocotb_labeler'):
    config = load_config(config_folder, processor_name)

    top_module = "processorci_top"
    language = "verilog"
    inc_dir = config['include_dirs']
    sim_files = config['files']
    language_version = config['language_version']

    # Write the Makefile content
    with open(makefile_path, 'a', encoding='utf-8') as makefile:
        makefile.write('SIM ?= verilator\n')
        makefile.write('TOPLEVEL_LANG ?= verilog\n')
        makefile.write(f'COMPILE_ARGS ?= --language 1800-{language_version} -DSIMULATION -Wno-fatal -Wno-lint\n')
        for dirs in inc_dir:
            path = escape_spaces(f'cores/{processor_name}/{dirs}')
            makefile.write(f'VERILOG_INCLUDE_DIRS += {path}\n')
        for file in sim_files:
            path = escape_spaces(f'cores/{processor_name}/{file}')
            makefile.write(f'VERILOG_SOURCES += {path}\n')
        makefile.write(f'VERILOG_SOURCES += processor_ci/internal/ahblite_to_wishbone.sv\n')
        makefile.write(f'VERILOG_SOURCES += processor_ci/internal/axi4lite_to_wishbone.sv\n')
        makefile.write(f'VERILOG_SOURCES += processor_ci/internal/axi4_to_wishbone.sv\n')
        makefile.write(f'VERILOG_SOURCES += {os.path.join(top_folder, f"{processor_name}.sv")}\n')
        makefile.write(f'TOPLEVEL = {top_module}\n')
        makefile.write(f'MODULE = {cocotb_name}\n')
        makefile.write(f'OUTPUT_DIR = {output_dir}/{processor_name}\n')
        makefile.write('export OUTPUT_DIR\n')
        makefile.write('include $(shell cocotb-config --makefiles)/Makefile.sim\n') 

    return makefile_path


def create_cocotb_makefile(processor_name: str, language: str, config_folder: str, top_folder: str, output_dir: str, cocotb_name: str = 'cocotb_labeler'):
    """Create a Makefile for cocotb simulation.

    Args:
        processor_name (str): Name of the processor.
        language (str): Programming language of the processor (e.g., 'verilog', 'systemverilog', 'vhdl').
        config_folder (str): Path to the configuration folder.
        top_folder (str): Path to folder containg all the top "shells".
        output_dir (str): Directory to save the generated Makefile.
        cocotb_name (str): Name of the cocotb module. Defaults to 'cocotb_labeler'.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s: %(message)s',
    )
    # Ensure the output folder exists
    os.makedirs(output_dir, exist_ok=True)

    processor_dir = os.path.join(output_dir, processor_name)
    # Ensure the processor directory exists
    os.makedirs(processor_dir, exist_ok=True)

    # Define the Makefile path
    makefile_path = os.path.join(processor_dir, f'{processor_name}.mk')

    # Check if the Makefile already exists
    if os.path.exists(makefile_path):
        os.remove(makefile_path)

    with open(makefile_path, 'w', encoding='utf-8') as makefile:
        makefile.write('# Makefile generated by create_cocotb_makefile.py\n')
        makefile.write('# Do not edit this file manually.\n')
        makefile.write('\n')

    # Check if the top folder exists
    if os.path.exists(top_folder):
        top_path = os.path.abspath(top_folder)

    # Check if there is a top file for the processor
    top_file = os.path.join(top_path, f'top_{processor_name}.sv')
    if not os.path.exists(top_file):
        logging.warning(f'Top file {top_file} does not exist. Simulating without processor_ci top file.')
        makefile_path = processor_top_makefile(
            processor_name, 
            config_folder, 
            top_path, 
            output_dir, 
            makefile_path, 
            cocotb_name
        )
    else:
        makefile_path = standard_makefile(
            processor_name, 
            language, 
            config_folder, 
            output_dir, 
            makefile_path, 
            cocotb_name
        )

    return makefile_path


def main(processor_name: str, config_folder: str, output_dir: str, cocotb_name: str):
    """Main function to create the cocotb Makefile.

    Args:
        processor_name (str): Name of the processor.
        config_folder (str): Path to the configuration file.
        output_dir (str): Directory to save the generated Makefile.
        cocotb_name (str): Name of the cocotb module.
    """
    makefile_path = create_cocotb_makefile(processor_name, config_folder, output_dir, cocotb_name)
    logging.info(f'Makefile created at: {makefile_path}')
    return makefile_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create a cocotb Makefile for simulation.')
    parser.add_argument(
        '-n', 
        '--name',
        type=str,
        required=True,
        help='Name of the processor.'
    )
    parser.add_argument(
        '-c',
        '--config',
        type=str,
        required=True,
        help='Path to the configuration folder.'
    )    
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        required=True,
        help='Directory to save the generated Makefile.'
    )
    parser.add_argument(
        '-l',
        '--cocotb_name',
        type=str,
        default='cocotb_labeler',
        help='Name of the cocotb module. Defaults to "cocotb_labeler".'
    )
    args = parser.parse_args()
    processor_name = args.name
    config_folder = args.config
    output_dir = args.output
    cocotb_name = args.cocotb_name
    main(processor_name, config_folder, output_dir, cocotb_name)
    