
"""
This script is responsible to generate a report if the processor is able to be simulable or not
"""

import subprocess
import os

def get_directories(path: str):
    """
    Returns a list of all directory names inside the given path.
    """
    try:
        return sorted([name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))], key=str.casefold)
    except FileNotFoundError:
        print(f"Directory not found: {path}")
        return []
    except PermissionError:
        print(f"Permission denied: {path}")
        return []


def run_command(cores: list):
    success: int = 0
    failed_cores = []
    successful_cores = []

    # List of keywords that determine fail in the execution
    fail_keywords = [
        "returned non-zero exit status"
    ]


    for core in cores:
        command = f"python processor_ci_utils/labeler/src/main.py -d cores/{core} -t processor_ci/rtl -c processor_ci/config"
        print(f"Now testing {core}")
        try:
            # Run the command and stores it's output
            result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)

            for keyword in fail_keywords:
                if keyword not in (result.stdout + "\n" + result.stderr):
                    print(f"{core} executed successfully!")
                    success+=1
                    successful_cores.append(core)
                else:
                    failed_cores.append(core)
                    print(f"{core} failed!")

        except:
            failed_cores.append(core)
            print(f"{core} failed!")

    return success, failed_cores, successful_cores

if __name__ == "__main__":
    # Get the processor names in the "cores" directory
    dirs = get_directories("cores")
    print(dirs)

    # dirs = ["airisc_core_complex', 'Anfield', 'arRISCado', 'Baby-Risco-5"]

    success, successful_cores, failed_cores = run_command(dirs)

    print(f"Successful cores: {successful_cores}")
    print(f"Failed cores: {failed_cores}")

    print(f"Successful simuations: {success} out of {len(dirs)}")