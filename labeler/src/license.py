import logging
import re
import subprocess
from collections import OrderedDict

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
    license_patterns = OrderedDict([
        # Copyleft
        ('GPLv3', (r'(?i)GNU GENERAL PUBLIC LICENSE\s*Version 3', 0)),
        ('GPLv2', (r'(?i)GNU GENERAL PUBLIC LICENSE\s*Version 2', 0)),
        ('LGPLv3', (r'(?i)Lesser General Public License\s*Version 3', 0)),
        ('LGPLv2.1', (r'(?i)Lesser General Public License\s*Version 2\.1', 0)),

        # Creative Commons
        ('Creative Commons Attribution-NonCommercial-NoDerivatives (CC BY-NC-ND)',
            (r'(?i)This work is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives', 0)),
        ('Creative Commons Attribution-NonCommercial-ShareAlike (CC BY-NC-SA)',
            (r'(?i)This work is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike', 0)),
        ('Creative Commons Attribution-NoDerivatives (CC BY-ND)',
            (r'(?i)This work is licensed under a Creative Commons Attribution-NoDerivatives', 0)),
        ('Creative Commons Attribution-NonCommercial (CC BY-NC)',
            (r'(?i)This work is licensed under a Creative Commons Attribution-NonCommercial', 0)),
        ('Creative Commons Attribution-ShareAlike (CC BY-SA)',
            (r'(?i)This work is licensed under a Creative Commons Attribution-ShareAlike', 0)),
        ('Creative Commons Attribution (CC BY)',
            (r'(?i)This work is licensed under a Creative Commons Attribution', 0)),
        ('CC0', (r'(?i)Creative Commons Zero', 0)),

        # BSD
        ('BSD 3-Clause', (
            r'''(?isx)
            \bRedistribution\s+and\s+use\s+in\s+source\s+and\s+binary\s+forms.*?
            \*.*?Redistributions\s+of\s+source\s+code\s+must\s+retain.*?
            \*.*?Redistributions\s+in\s+binary\s+form\s+must\s+reproduce.*?
            \*.*?Neither\s+the\s+name\s+of\s+.*?nor\s+the\s+names\s+of\s+its\s+contributors.*?
            permission
            ''',
            re.VERBOSE
        )),
        ('BSD 2-Clause', (
            r'(?is)Redistribution and use in source and binary forms, with or without modification, '
            r'are permitted provided that the following conditions are met:.*?'
            r'1\.\s*Redistributions of source code must retain.*?copyright.*?'
            r'2\.\s*Redistributions in binary form must reproduce.*?in the documentation.*?'
            r'THIS SOFTWARE IS PROVIDED.*?AS IS(?!.*?neither the name)',
            0
        )),

        # Solderpad
        ('Solderpad', (
            r'(?is)Solderpad(?: Hardware)? License.*?Version\s*(\d+(?:\.\d+)+)', 0
        )),

        # Permissive
        ('MIT', (r'(?i)permission is hereby granted, free of charge, to any person obtaining a copy', 0)),
        ('Apache 2.0', (r'(?is)Apache License\s*Version 2\.0', 0)),
        ('Apache 1.1', (r'(?is)Apache Software License\s+Version 1\.1', 0)),
        ('Apache 1.0', (r'(?is)Apache Software License\s+Version 1\.0', 0)),
        ('ISC', (
            r'(?i)Permission to use, copy, modify, and distribute this software for any '
            r'purpose(?:\n|\s)*with or without fee is hereby granted, provided that the above '
            r'copyright notice(?:\n|\s)*and this permission notice appear in all copies\.(?:\n|\s)*'
            r'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES(?:\n|\s)*'
            r'INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS '
            r'FOR A PARTICULAR PURPOSE\.',
            0
        )),
        ('Zlib', (r'(?i)This software is provided \'as-is\', without any express or implied warranty', 0)),
        ('Unlicense', (r'(?i)This is free and unencumbered software released into the public domain', 0)),

        # CERN OHL
        ('CERN Open Hardware Licence v2 - Strongly Reciprocal',
            (r'(?i)The CERN-OHL-S is copyright CERN 2020\.', 0)),
        ('CERN Open Hardware Licence v2 - Weakly Reciprocal',
            (r'(?i)The CERN-OHL-W is copyright CERN 2020\.', 0)),
        ('CERN Open Hardware Licence v2 - Permissive',
            (r'(?i)The CERN-OHL-P is copyright CERN 2020\.', 0)),

        # Other
        ('Eclipse Public License', (r'(?i)Eclipse Public License - v [0-9]\.[0-9]', 0)),
        ('MPL 2.0', (r'(?i)Mozilla Public License\s*Version 2\.0', 0)),
        ('Public Domain', (r'(?i)dedicated to the public domain', 0)),
        ('Proprietary', (r'(?i)\ball rights reserved\b.*?(license|copyright|terms)', 0)),
        ('Artistic License', (r'(?i)This package is licensed under the Artistic License', 0)),
        ('Academic Free License', (r'(?i)Academic Free License', 0)),
    ])

    for license_name, (pattern, flags) in license_patterns.items():
        compiled_pattern = re.compile(pattern, flags)
        if compiled_pattern.search(license_content):
            return license_name
    return 'Custom License'
