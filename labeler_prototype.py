"""A prototype script to find LICENSE files in a directory and identify their types."""
import subprocess
import re
import json
import argparse
import os
import logging
import cocotb
import shlex
import sys
module_path = os.path.abspath(os.path.join('..','/eda/processor_ci/core'))
if module_path not in sys.path:
    sys.path.append(module_path)
from config import load_config

EXTENSIONS = ['v', 'sv', 'vhdl', 'vhd']

def find_license_files(directory: str) -> list[str]:
    """Find all LICENSE files in the given directory.

    Args:
        directory (str): The directory to search for LICENSE files.

    Returns:
        list: A list of LICENSE file paths.
    """
    logging.basicConfig(
        level=logging.WARNING, format='%(levelname)s: %(message)s'
    )

    try:
        result = subprocess.run(
            ['find', directory, '-type', 'f', '-iname', '*LICENSE*'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        if result.stderr:
            logging.warning('Error: %s', result.stderr)
            return []
        return (
            result.stdout.strip().split('\n') if result.stdout.strip() else []
        )
    except subprocess.CalledProcessError as e:
        logging.warning('Error executing find command: %s', e)
        return []
    except FileNotFoundError as e:
        logging.warning('Find command not found: %s', e)
        return []


def identify_license_type(license_content):
    """Identify the type of license based on the content of the LICENSE file.

    Args:
        license_content (str): The content of the LICENSE file.

    Returns:
        str: The type of license.
    """
    license_patterns = {
        # Permissive Licenses
        'MIT': r'(?i)permission is hereby granted, free of charge, to any person obtaining a copy',
        'Apache 2.0': r'(?i)licensed under the Apache License, Version 2\.0',
        'BSD 2-Clause': (
            r'(?i)Redistribution and use in source and binary forms, with or without modification, '
            r'are permitted provided that the following conditions are met:\s*'
            r'1\.\s*Redistributions of source code must retain the above copyright notice, '
            r'this list of conditions and the following disclaimer\.\s*'
            r'2\.\s*Redistributions in binary form must reproduce the above copyright notice, '
            r'this list of conditions and the following disclaimer in the documentation '
            r'and/or other materials provided with the distribution\.\s*'
            r'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"'
        ),
        'BSD 3-Clause': (
            r'(?i)neither the name of the copyright holder nor the names of its\s+contributors '
            r'may be used to endorse or promote products derived from\s+this '
            r'software without specific prior written permission\.'
        ),
        'ISC': (
            r'(?i)Permission to use, copy, modify, and distribute this software for any '
            r'purpose(?:\n|\s)*with or without fee is hereby granted, provided that the above '
            r'copyright notice(?:\n|\s)*and this permission notice appear in all copies\.(?:\n|\s)*'
            r'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES(?:\n|\s)*'
            r'INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS '
            r'FOR A PARTICULAR PURPOSE\.'
        ),
        # Other licenses...
        'Zlib': (
            r'(?i)This software is provided \'as-is\', without any express or implied warranty'
        ),
        'Unlicense': (
            r'(?i)This is free and unencumbered software released into the public domain'
        ),
        # CERN Open Hardware Licenses
        'CERN Open Hardware Licence v2 - Permissive': r'(?i)The CERN-OHL-P is copyright CERN 2020.',
        'CERN Open Hardware Licence v2 - Weakly Reciprocal': (
            r'(?i)The CERN-OHL-W is copyright CERN 2020.'
        ),
        'CERN Open Hardware Licence v2 - Strongly Reciprocal': (
            r'(?i)The CERN-OHL-S is copyright CERN 2020.'
        ),
        # Copyleft Licenses
        'GPLv2': r'(?i)GNU GENERAL PUBLIC LICENSE\s*Version 2',
        'GPLv3': r'(?i)GNU GENERAL PUBLIC LICENSE\s*Version 3',
        'LGPLv2.1': r'(?i)Lesser General Public License\s*Version 2\.1',
        'LGPLv3': r'(?i)Lesser General Public License\s*Version 3',
        'MPL 2.0': r'(?i)Mozilla Public License\s*Version 2\.0',
        'Eclipse Public License': r'(?i)Eclipse Public License - v [0-9]\.[0-9]',
        # Creative Commons Licenses
        'CC0': r'(?i)Creative Commons Zero',
        'Creative Commons Attribution (CC BY)': (
            r'(?i)This work is licensed under a Creative Commons Attribution'
        ),
        'Creative Commons Attribution-ShareAlike (CC BY-SA)': (
            r'(?i)This work is licensed under a Creative Commons Attribution-ShareAlike'
        ),
        'Creative Commons Attribution-NoDerivatives (CC BY-ND)': (
            r'(?i)This work is licensed under a Creative Commons Attribution-NoDerivatives'
        ),
        'Creative Commons Attribution-NonCommercial (CC BY-NC)': (
            r'(?i)This work is licensed under a Creative Commons Attribution-NonCommercial'
        ),
        'Creative Commons Attribution-NonCommercial-ShareAlike (CC BY-NC-SA)': (
            r'(?i)This work is licensed under a Creative Commons '
            r'Attribution-NonCommercial-ShareAlike'
        ),
        'Creative Commons Attribution-NonCommercial-NoDerivatives (CC BY-NC-ND)': (
            r'(?i)This work is licensed under a Creative Commons '
            r'Attribution-NonCommercial-NoDerivatives'
        ),
        # Public Domain
        'Public Domain': r'(?i)dedicated to the public domain',
        # Proprietary Licenses
        'Proprietary': r'(?i)\ball rights reserved\b.*?(license|copyright|terms)',
        # Academic and Other Specialized Licenses
        'Artistic License': r'(?i)This package is licensed under the Artistic License',
        'Academic Free License': r'(?i)Academic Free License',
    }

    for license_name, pattern in license_patterns.items():
        if re.search(pattern, license_content):
            return license_name
    return 'Custom License'


def create_cocotb_makefile(processor_name: str, config_file: str, output_dir: str):
    """Create a Makefile for cocotb simulation.

    Args:
        processor_name (str): Name of the processor.
        config_file (str): Path to the configuration file.
        output_dir (str): Directory to save the generated Makefile.
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

    # Load the configuration file
    config = load_config(config_file, processor_name)

    #Load the processor configuration
    inc_dir = config['include_dirs']
    sim_files = config['files']
    top_module = config['top_module']

    # Check which language to use
    if any(file.endswith('.v') for file in sim_files):
        language = 'verilog'
    elif any(file.endswith('.sv') for file in sim_files):
        language = 'systemverilog'
    elif any(file.endswith('.vhdl') or file.endswith('.vhd') for file in sim_files):
        language = 'vhdl'
    else:
        raise ValueError("No valid source files found.")

    # Write the Makefile content
    with open(makefile_path, 'a', encoding='utf-8') as makefile:
        if language == 'verilog':
            makefile.write('SIM ?= icarus\n')
            makefile.write('TOPLEVEL_LANG ?= verilog\n')
            for dirs in inc_dir:
                makefile.write(f'VERILOG_INCLUDE_DIRS = /jenkins/jenkins_home/workspace/{processor_name}/{processor_name}/{dirs}\n')
            for file in sim_files:
                makefile.write(f'VERILOG_SOURCES += /jenkins/jenkins_home/workspace/{processor_name}/{processor_name}/{file}\n')
        elif language == 'systemverilog':
            makefile.write('SIM ?= verilator\n')
            makefile.write('TOPLEVEL_LANG ?= systemverilog\n')
            for dirs in inc_dir:
                makefile.write(f'SYSTEMVERILOG_INCLUDE_DIRS = /jenkins/jenkins_home/workspace/{processor_name}/{processor_name}/{dirs}\n')
            for file in sim_files:
                makefile.write(f'SYSTEMVERILOG_SOURCES += /jenkins/jenkins_home/workspace/{processor_name}/{processor_name}/{file}\n')
        elif language == 'vhdl':
            makefile.write('SIM ?= ghdl\n')
            makefile.write('TOPLEVEL_LANG ?= vhdl\n')
            for dirs in inc_dir:
                makefile.write(f'VHDL_INCLUDE_DIRS = /jenkins/jenkins_home/workspace/{processor_name}/{processor_name}/{dirs}\n')
            for file in sim_files:
                makefile.write(f'VHDL_SOURCES += /jenkins/jenkins_home/workspace/{processor_name}/{processor_name}/{file}\n')
        makefile.write(f'TOPLEVEL = {top_module}\n')
        makefile.write('MODULE = cocotb_labeler\n')
        makefile.write(f'OUTPUT_DIR = {output_dir}/{processor_name}\n')
        makefile.write('export OUTPUT_DIR\n')
        makefile.write('include $(shell cocotb-config --makefiles)/Makefile.sim\n')

    return makefile_path


def generate_labels_file(
    processor_name, license_types, cpu_bits, cache, output_dir
):
    """Generate a JSON file with labels for the processor.

    Args:
        processor_name (str): The name of the processor.
        license_types (list{str}): List of license types.
        cpu_bits (int): CPU bit architecture.
        cache (bool): True if the CPU has cache, False otherwise.
        output_dir (str): The folder where the JSON file will be saved.
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

    # Define the output file path using the processor name
    output_file = os.path.join(processor_dir, f'{processor_name}_labels.json')

    # Ensure the JSON file exists
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
        'license_types': list(set(license_types)),  # Deduplicate license types
        'bits': cpu_bits,
        'cache': cache,
    }

    # Write updated results back to JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(existing_data, json_file, indent=4)
        print(f'Results saved to {output_file}')
    except OSError as e:
        logging.warning('Error writing to JSON file: %s', e)


def core_labeler(directory, config_file, output_dir):
    """Main function to find LICENSE files and generate labels.

    Args:
        directory (str): The directory to search for LICENSE files.
        config_file (str): Path to the configuration file.
        output_dir (str): Directory to save the generated files.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s: %(message)s',
    )
    # Find all LICENSE files in the directory
    license_files = find_license_files(directory)

    if not license_files:
        logging.warning('No LICENSE files found in the directory.')
        return

    license_types = []

    for license_file in license_files:
        try:
            with open(license_file, 'r', encoding='utf-8') as file:
                content = file.read()
                license_type = identify_license_type(content)
                license_types.append(license_type)
        except OSError as e:
            logging.warning('Error reading file %s: %s', license_file, e)
            license_types.append('Error')

    # Create a Makefile for cocotb simulation
    processor_name = os.path.basename(os.path.normpath(directory))
    makefile = create_cocotb_makefile(processor_name, config_file, output_dir)

    cpu_bits = None
    cache = False
    generate_labels_file(processor_name, license_types, cpu_bits, cache, output_dir)

    ##venv_path = "/eda/processor_ci_utils/env"
    bash_command = f"make -f {makefile} clean && make -f {makefile}"

    try:
        subprocess.run(bash_command, shell=True, check=True, executable="/bin/bash")
    except subprocess.CalledProcessError as e:
        logging.warning('Error executing make command: %s', e)
        return

def main(directory, config_directory, output_directory):
    """Main function to execute the core labeler.

    Args:
        directory (str): The directory to search for cores files.
        config_directory (str): The directory containing the configuration files.
        output_directory (str): The directory to save the generated files.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s: %(message)s',
    )
    # Ensure the output folder exists
    os.makedirs(output_directory, exist_ok=True)

    # Get all subdirectories in the given directory
    subdirectories = [
        os.path.join(directory, d)
        for d in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, d))
    ]

    for subdirectory in subdirectories:
        if ('@' in subdirectory):
            continue
        core_labeler(
            subdirectory,
            config_directory,
            output_directory,
        )
        print(f'Processed {subdirectory}')

        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Find parameters of a RISC-V based CPU.'
    )
    parser.add_argument(
        '-d',
        '--dir',
        help='The directory to search for LICENSE files.',
        required=True,
    )
    parser.add_argument(
        '-c',
        '--config',
        default='config.json',
        help='The configuration file path.',
    )
    parser.add_argument(
        '-o',
        '--output',
        default='cores_utils',
        help='The output folder path.',
    )
    parser.add_argument(
        '-b',
        '--batch',
        default=False,
        help='Run in batch mode.',
    )
    args = parser.parse_args()
    dir_to_search = args.dir
    config_json = args.config
    output_folder = args.output
    batch_mode = args.batch
    if batch_mode:
        # Run in batch mode
        main(dir_to_search, config_json, output_folder)
    else:
        # Run in interactive mode
        core_labeler(
            dir_to_search,
            config_json,
            output_folder,
        )