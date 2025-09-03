
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
        command = f"python3 labeler/src/main.py -d cores/{core} -t ../processor_ci/rtl -c ../processor_ci/config"
        print(f"Now testing {core}")
        try:
            # Run the command and stores it's output
            result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
            print(f"Command output: {result.stdout}")
            print(f"Command error (if any): {result.stderr}")

            failure_detected = False
            for keyword in fail_keywords:
                if keyword in (result.stdout + "\n" + result.stderr):
                    failed_cores.append(core)
                    print(f"{core} failed!")
                    print(f"Error output: {result.stderr}")
                    if result.stdout:
                        print(f"Standard output: {result.stdout}")
                    failure_detected = True
                    break
            
            if not failure_detected:
                print(f"{core} executed successfully!")
                success+=1
                successful_cores.append(core)

        except subprocess.CalledProcessError as e:
            failed_cores.append(core)
            print(f"{core} failed with exit code {e.returncode}!")
            print(f"Error output: {e.stderr}")
            if e.stdout:
                print(f"Standard output: {e.stdout}")
        except Exception as e:
            failed_cores.append(core)
            print(f"{core} failed with exception: {str(e)}")

    return success, failed_cores, successful_cores

if __name__ == "__main__":
    # Get the processor names in the "cores" directory
    dirs = get_directories("cores")
    print(dirs)

    # dirs = ["airisc_core_complex', 'Anfield', 'arRISCado', 'Baby-Risco-5"]

    success, failed_cores, successful_cores = run_command(dirs)

    print(f"Successful cores: {successful_cores}")
    print(f"Failed cores: {failed_cores}")

    print(f"Successful simulations: {success} out of {len(dirs)}")