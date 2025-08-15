import cocotb
from cocotb.handle import NonHierarchyIndexableObject
import re
import os
import json


def find_reg_bank(dut, submodule_attr, signals_list):
    if signals_list == None: # starting with dut
        signals_list = []
    if submodule_attr == None:
        tmp_top_list = dir(dut)

        top_submodules = []
        for item in tmp_top_list:
            # get only valid signal/submodules
            if item[0] != '_' and item != "get_definition_name" and item != "get_definition_file":
                # check whether it is a signal or a submodule
                item_dir = dir(getattr(dut, item))
                if item_dir[-1] == 'value':
                    try:
                        value = getattr(dut, item)
                        if isinstance(value, NonHierarchyIndexableObject) and len(set(str(value.value).lower())) > 2:
                                signals_list.append([dut, item])
                    except IndexError:
                        pass
                    except TypeError:   
                        pass
                else:
                    top_submodules.append(item)
        for submodule in top_submodules:
            submodule_attr = getattr(dut, submodule)
            find_reg_bank(dut, submodule_attr, signals_list)
    else:
        tmp_submodule_list = dir(submodule_attr)

        submodule_submodules = []
        for item in tmp_submodule_list:
            # get only valid signal/submodules
            if item[0] != '_' and item != "get_definition_name" and item != "get_definition_file":
                # check whether it is a signal or a submodule
                item_dir = dir(getattr(submodule_attr, item))
                if item_dir[-1] == 'value':
                    try:
                        value = getattr(submodule_attr, item)
                        if isinstance(value, NonHierarchyIndexableObject) and len(set(str(value.value).lower())) > 2:
                                signals_list.append([submodule_attr, item])
                    except IndexError:
                        pass
                    except TypeError: 
                        pass
                else:
                    submodule_submodules.append(item)
        for submodule in submodule_submodules:
            if len(submodule_submodules) != 0:
                new_submodule_attr = getattr(submodule_attr, submodule)
                find_reg_bank(dut, new_submodule_attr, signals_list)
    return signals_list

def count_bits(dut, signals_list):
    """Find the register bank in the list of signals.

    Args:
        signals_list: List of signals.

    Returns:
        The register bank signal if found, otherwise None.
    """

    signals_list = find_reg_bank(dut, None, None)

    if len(signals_list) == 0:
        print("No register_bank found")
        return None
    elif len(signals_list) == 1:
        return len(getattr(signals_list[0][0], signals_list[0][1])[0])
    else:
        for signal in signals_list:
            if len(getattr(signal[0], signal[1])[0]) == 32 or len(getattr(signal[0], signal[1])[0]) == 64:
                return len(getattr(signal[0], signal[1])[0])